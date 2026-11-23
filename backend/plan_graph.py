import json
import os
from typing import TypedDict

from langchain_litellm import ChatLiteLLM
from langgraph.graph import END, START, StateGraph

from onboarding_tools import make_plan

MAX_DRAFTS = 3  # first draft + 2 retries, then we fall back to the plain template


class PlanState(TypedDict, total=False):
    role: str
    start_date: str
    spoil: bool        # demo switch: damages the first draft so you can show the recovery
    base: dict         # the template plan from onboarding_tools. Dates come from here, never from the LLM
    draft: list | None # planner output: [{"date", "task"}]
    feedback: str      # what the reviewer didn't like
    attempts: int
    approved: bool
    result: dict
    source: str        # "agent" or "fallback"


def make_llm():
    provider = os.environ.get("LLM_PROVIDER", "groq").lower()
    if provider == "bedrock":
        model = f"bedrock/{os.environ['BEDROCK_MODEL_ID']}"
    elif provider == "groq":
        model = f"groq/{os.environ.get('GROQ_FREE_MODEL', 'openai/gpt-oss-20b')}"
    else:
        raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Use 'groq' or 'bedrock'.")
    return ChatLiteLLM(model=model, temperature=0, max_tokens=4000)


def parse_json(text:str) -> dict:
    # models sometimes wrap JSON in ```json fences or add a sentence around it
    return json.loads(text[text.index("{"): text.rindex("}") + 1])


def review_rules(base:dict, draft:list) -> str:
    """Hard checks, no LLM. Returns a feedback string, or "" if the draft is fine."""
    expected = [d["date"] for d in base["plan"]]
    got = [d.get("date") for d in draft]
    if got != expected:
        return f"The dates must be exactly these, in order: {expected}. You returned: {got}."
    if any(not isinstance(d.get("task"), str) or not d["task"].strip() or len(d["task"]) > 200 for d in draft):
        return "Every task must be a non-empty string of at most 200 characters."
    if "access" not in draft[0]["task"].lower():
        return "Day 1 must be about getting access set up."
    return ""


def build_graph(llm):
    async def planner(state:PlanState) -> dict:
        attempts = state.get("attempts", 0) + 1
        prompt = (
            "You are the Planner for a new-joiner onboarding plan.\n"
            f"Role: {state['role']}. Rewrite each task so it is friendly and specific to the role. "
            "Keep the meaning. Do not add, remove or reorder days. Keep every date exactly as given.\n"
            f"Template plan:\n{json.dumps(state['base']['plan'])}\n"
        )
        if state.get("feedback"):
            prompt += f"Your last draft was rejected. Reviewer feedback: {state['feedback']}\n"
        prompt += 'Reply with JSON only: {"plan": [{"date": "YYYY-MM-DD", "task": "..."}]}'
        try:
            draft = parse_json((await llm.ainvoke(prompt)).content)["plan"]
        except Exception as e:
            return {"attempts": attempts, "draft": None, "feedback": f"Your reply was not valid JSON in the right shape ({type(e).__name__})."}
        if state.get("spoil") and attempts == 1 and draft:
            draft[-1]["date"] = "1999-01-02"  # demo only: break the first draft so the reviewer has something to catch
        return {"attempts": attempts, "draft": draft}

    async def reviewer(state:PlanState) -> dict:
        draft = state.get("draft")
        if draft is None:
            return {"approved": False}  # planner already wrote the feedback
        problem = review_rules(state["base"], draft)
        if not problem:
            prompt = (
                "You are the Reviewer for a new-joiner onboarding plan. Check the tasks are professional, "
                'friendly and sensible for the role. Reply with JSON only: {"ok": true or false, "feedback": "..."}\n'
                f"Role: {state['role']}\nTasks: {json.dumps([d['task'] for d in draft])}"
            )
            try:
                verdict = parse_json((await llm.ainvoke(prompt)).content)
                if verdict.get("ok") is False:
                    problem = str(verdict.get("feedback", "Tone or content needs work."))
            except Exception:
                pass  # shortcut: if the reviewer LLM fails we trust the rule checks alone; tighten when the plan matters more
        if problem:
            return {"approved": False, "feedback": problem}
        merged = [{**b, "task": d["task"]} for b, d in zip(state["base"]["plan"], draft)]
        return {"approved": True, "result": {**state["base"], "plan": merged}, "source": "agent"}

    async def fallback(state:PlanState) -> dict:
        return {"result": state["base"], "source": "fallback"}

    def after_review(state:PlanState) -> str:
        if state.get("approved"):
            return END
        return "planner" if state["attempts"] < MAX_DRAFTS else "fallback"

    graph = StateGraph(PlanState)
    graph.add_node("planner", planner)
    graph.add_node("reviewer", reviewer)
    graph.add_node("fallback", fallback)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "reviewer")
    graph.add_conditional_edges("reviewer", after_review, ["planner", "fallback", END])
    graph.add_edge("fallback", END)
    return graph.compile()


async def run_plan(llm, role:str, start_date:str, spoil:bool=False):
    """Yields progress events, then a final {"event": "result", ...}. Raises ValueError for a bad role or date."""
    base = make_plan(role, start_date)
    graph = build_graph(llm)
    state = {"role": role, "start_date": start_date, "spoil": spoil, "base": base}
    async for update in graph.astream(state, stream_mode="updates"):
        for node, out in update.items():
            if node == "planner":
                yield {"event": "progress", "step": "planner", "attempt": out["attempts"]}
            elif node == "reviewer":
                yield {"event": "progress", "step": "reviewer", "approved": out["approved"], "feedback": out.get("feedback", "")}
            elif node == "fallback":
                yield {"event": "progress", "step": "fallback"}
            if "result" in out:
                yield {"event": "result", "source": out["source"], **out["result"]}
