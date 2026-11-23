import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import main
from onboarding_tools import make_plan
from plan_graph import MAX_DRAFTS, run_plan

from test_api import HEADERS, parse_sse

client = TestClient(main.app)
BASE = make_plan("developer", "2026-12-01")


class FakeLLM:
    """Planner prompts get a friendly rewrite of the template. Reviewer prompts get a verdict from `verdicts`."""

    def __init__(self, planner_replies=None, verdicts=None):
        self.planner_replies = list(planner_replies or [])
        self.verdicts = list(verdicts or [])
        self.planner_prompts = []

    async def ainvoke(self, prompt):
        if "You are the Planner" in prompt:
            self.planner_prompts.append(prompt)
            if self.planner_replies:
                return SimpleNamespace(content=self.planner_replies.pop(0))
            plan = [{"date": d["date"], "task": "Friendly: " + d["task"]} for d in BASE["plan"]]
            if "Get your access" not in plan[0]["task"]:
                raise AssertionError("template changed")
            return SimpleNamespace(content="```json\n" + json.dumps({"plan": plan}) + "\n```")
        verdict = self.verdicts.pop(0) if self.verdicts else {"ok": True, "feedback": ""}
        return SimpleNamespace(content=json.dumps(verdict))


def collect(llm, role="developer", **kwargs):
    async def go():
        return [e async for e in run_plan(llm, role, "2026-12-01", **kwargs)]
    return asyncio.run(go())


def steps(events):
    return [(e["step"], e.get("attempt", e.get("approved"))) for e in events if e["event"] == "progress"]


def test_happy_path_uses_agent_rewrite():
    events = collect(FakeLLM())
    assert steps(events) == [("planner", 1), ("reviewer", True)]
    result = events[-1]
    assert result["source"] == "agent"
    assert result["plan"][0]["task"].startswith("Friendly:")
    assert [d["date"] for d in result["plan"]] == [d["date"] for d in BASE["plan"]]  # dates always come from the template


def test_spoiled_first_draft_is_caught_and_recovered():
    llm = FakeLLM()
    events = collect(llm, spoil=True)
    assert steps(events) == [("planner", 1), ("reviewer", False), ("planner", 2), ("reviewer", True)]
    assert events[-1]["source"] == "agent"
    assert "Reviewer feedback" in llm.planner_prompts[1]  # the retry actually saw the feedback


def test_reviewer_llm_rejection_triggers_retry():
    events = collect(FakeLLM(verdicts=[{"ok": False, "feedback": "Too casual"}, {"ok": True}]))
    assert steps(events)[:3] == [("planner", 1), ("reviewer", False), ("planner", 2)]
    assert events[-1]["source"] == "agent"


def test_bad_json_every_time_falls_back_to_template():
    events = collect(FakeLLM(planner_replies=["not json"] * MAX_DRAFTS))
    assert [s for s in steps(events) if s[0] == "planner"] == [("planner", i) for i in range(1, MAX_DRAFTS + 1)]
    assert steps(events)[-1] == ("fallback", None)
    assert events[-1]["source"] == "fallback"
    assert events[-1]["plan"] == BASE["plan"]


def test_llm_crash_falls_back():
    class Broken:
        async def ainvoke(self, prompt): raise RuntimeError("rate limited")
    events = collect(Broken())
    assert events[-1]["source"] == "fallback"


def test_bad_role_raises():
    with pytest.raises(ValueError):
        collect(FakeLLM(), role="chef")


def test_plan_endpoint_streams_progress_and_result(monkeypatch):
    monkeypatch.setattr(main, "make_llm", lambda: FakeLLM())
    r = client.post("/plan/stream", json={"role": "developer", "start_date": "2026-12-01", "spoil_first_draft": True}, headers=HEADERS)
    names = [n for n, _ in parse_sse(r.text)]
    assert names == ["progress"] * 4 + ["result", "done"]
    assert parse_sse(r.text)[-2][1]["source"] == "agent"


def test_plan_endpoint_bad_role_is_422():
    r = client.post("/plan/stream", json={"role": "chef", "start_date": "2026-12-01"}, headers=HEADERS)
    assert r.status_code == 422


def test_plan_endpoint_needs_key():
    r = client.post("/plan/stream", json={"role": "developer", "start_date": "2026-12-01"})
    assert r.status_code == 401
