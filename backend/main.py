import os
import json
import secrets
from datetime import date
from dotenv import load_dotenv
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from strands import Agent
from strands.models import BedrockModel
from strands.models.litellm import LiteLLMModel

from guardrails import REFUSAL, check_input, clean_output
from onboarding_tools import build_30_day_plan, get_access_checklist, make_plan, search_company_docs
from plan_graph import make_llm, run_plan

load_dotenv()
app = FastAPI(title = "Onboarding Buddy API", version="0.5.0")

# Shows an "Authorize" button in /docs. auto_error=False so we return our own 401
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def check_api_key(api_key:str|None = Depends(api_key_header)):
    expected = os.environ.get("API_KEY", "")
    # No API_KEY configured means everything is rejected, so a forgotten setting can't leave the API open
    if not expected or not api_key or not secrets.compare_digest(api_key.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Missing or wrong API key")


class ChatRequest(BaseModel):
    message: str


class PlanRequest(BaseModel):
    role: str
    start_date: str
    spoil_first_draft: bool = False  # demo switch, see plan_graph.py


class Assistant:
    def __init__(self, system_prompt:str="", max_tokens:int=10000, max_retries:int=1, reasoning_effort:str="high"):
        self.system_prompt = system_prompt if system_prompt else f"""
        You are Onboarding Buddy, a friendly assistant that helps new joiners through their first 30 days.
        Today is {date.today():%A, %Y-%m-%d}.
        Use build_30_day_plan when asked for a plan. Ask for the role and start date if you don't have them.
        Use get_access_checklist when asked what access or tools someone needs.
        Use search_company_docs for questions about company policies and how things work, such as leave, expenses, IT, security or benefits.
        Answer those only from what search_company_docs returns, quote exact numbers, and say you don't know if it has no answer.
        Never make up dates, access items or policy details. Only help with onboarding questions. Keep answers short and clear.
        """
        # LLM_PROVIDER picks the model backend: "groq" (default) or "bedrock"
        self.provider = os.environ.get("LLM_PROVIDER", "groq").lower()
        # LiteLLM needs the "groq/" prefix to know which provider to use
        self.model_name = f"groq/{os.environ.get('GROQ_FREE_MODEL', 'openai/gpt-oss-20b')}"
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.reasoning_effort = reasoning_effort

        self.agent = self.init_agent()

    def init_llm_model(self):
        if self.provider == "bedrock":
            return self.init_bedrock_model()
        if self.provider != "groq":
            raise ValueError(f"Unknown LLM_PROVIDER '{self.provider}'. Use 'groq' or 'bedrock'.")
        return LiteLLMModel(
            model_id=self.model_name,
            params={
                "temperature": 0,
                "max_tokens": self.max_tokens,
                "num_retries": self.max_retries,
                "reasoning_effort": self.reasoning_effort
            }
        )

    def init_bedrock_model(self):
        # AWS keys come from the environment (loaded from .env) or the AWS CLI profile
        return BedrockModel(
            model_id=os.environ["BEDROCK_MODEL_ID"],
            region_name=os.environ.get("AWS_REGION", "ap-southeast-2"),
            temperature=0,
            max_tokens=self.max_tokens
        )

    def init_agent(self):
        return Agent(
            model=self.init_llm_model(),
            system_prompt=self.system_prompt,
            tools=[build_30_day_plan, get_access_checklist, search_company_docs],
            callback_handler=None  # stops it printing to the terminal
        )

    async def generate_response(self, message:str) -> AsyncIterator[str]:
        async for event in self.agent.stream_async(message):
            text = event.get("data")  # pieces of the answer text. Tool calls and other events have no "data"
            if text:
                yield text

    async def sse_events(self, message:str) -> AsyncIterator[str]:
        try:
            if check_input(message):   # blocked before the model sees it. Same stream shape, so clients need no special case
                yield f"data: {json.dumps({'text': REFUSAL})}\n\n"
                yield "event: done\ndata: {}\n\n"
                return
            async for text in self.generate_response(message):
                yield f"data: {json.dumps({'text': clean_output(text)})}\n\n"
            yield "event: done\ndata: {}\n\n"
        except Exception as e:
            yield f"event: error\ndata:{json.dumps({'error': str(e)})}\n\n"




@app.get("/health-check")
def health():
    return {"status": "ok"}

@app.post("/chat/stream", dependencies=[Depends(check_api_key)])
async def chat_stream(req:ChatRequest):
    assistant_manager = Assistant(reasoning_effort="low")
    return StreamingResponse(
        assistant_manager.sse_events(req.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/plan/stream", dependencies=[Depends(check_api_key)])
async def plan_stream(req:PlanRequest):
    try:
        make_plan(req.role, req.start_date)  # check role and date now so a bad request gets a 422, not a broken stream
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    async def events() -> AsyncIterator[str]:
        try:
            async for item in run_plan(make_llm(), req.role, req.start_date, req.spoil_first_draft):
                name = item.pop("event")
                yield f"event: {name}\ndata: {json.dumps(item)}\n\n"
            yield "event: done\ndata: {}\n\n"
        except Exception as e:
            yield f"event: error\ndata:{json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
