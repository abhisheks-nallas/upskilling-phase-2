import json

import pytest

from fastapi.testclient import TestClient
from strands.models import Model

import main


class FakeModel(Model):
    """Pretends to be the LLM. First turn: asks for the access checklist. Second turn: reads the tool result and answers."""

    def update_config(self, **kwargs): pass
    def get_config(self): return {}
    async def structured_output(self, *args, **kwargs): raise NotImplementedError

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        last = messages[-1]["content"][0]
        yield {"messageStart": {"role": "assistant"}}
        if "toolResult" in last:
            answer = "You need: " + last["toolResult"]["content"][0]["text"]
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": answer}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
        else:
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": "t1", "name": "get_access_checklist"}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps({"role": "qa"})}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}


client = TestClient(main.app)
HEADERS = {"X-API-Key": "test-key"}


def parse_sse(body:str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(":", 1) for line in block.split("\n"))
        events.append((lines.get("event", "message").strip(), json.loads(lines["data"])))
    return events


def test_health_check():
    assert client.get("/health-check").json() == {"status": "ok"}


def test_chat_stream_runs_tool_and_streams_answer(monkeypatch):
    monkeypatch.setattr(main.Assistant, "init_llm_model", lambda self: FakeModel())
    response = client.post("/chat/stream", json={"message": "What access does a QA need?"}, headers=HEADERS)
    assert response.headers["content-type"].startswith("text/event-stream")

    events = parse_sse(response.text)
    assert events[-1][0] == "done"
    text = "".join(data["text"] for name, data in events if name == "message")
    assert "Staging environment" in text  # came from the real tool, through the agent


def test_chat_stream_sends_error_event_when_model_fails(monkeypatch):
    async def broken(self, message):
        raise RuntimeError("model is down")
        yield  # makes this an async generator

    monkeypatch.setattr(main.Assistant, "init_llm_model", lambda self: FakeModel())
    monkeypatch.setattr(main.Assistant, "generate_response", broken)
    events = parse_sse(client.post("/chat/stream", json={"message": "hi"}, headers=HEADERS).text)
    assert events == [("error", {"error": "model is down"})]


def test_chat_stream_rejects_missing_message():
    assert client.post("/chat/stream", json={}, headers=HEADERS).status_code == 422


def test_provider_defaults_to_groq_with_20b_model(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GROQ_FREE_MODEL", raising=False)
    assistant = main.Assistant()
    assert assistant.model_name == "groq/openai/gpt-oss-20b"


def test_provider_can_switch_to_bedrock(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model-id")
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")  # fake, no call is made
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    assistant = main.Assistant()
    assert isinstance(assistant.agent.model, main.BedrockModel)
    assert assistant.agent.model.get_config()["model_id"] == "test-model-id"


def test_unknown_provider_fails_clearly(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nope")
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        main.Assistant()


def test_chat_stream_rejects_missing_or_wrong_key():
    body = {"message": "hi"}
    assert client.post("/chat/stream", json=body).status_code == 401
    assert client.post("/chat/stream", json=body, headers={"X-API-Key": "wrong"}).status_code == 401


def test_chat_stream_rejects_everything_when_server_has_no_key(monkeypatch):
    monkeypatch.delenv("API_KEY")
    assert client.post("/chat/stream", json={"message": "hi"}, headers={"X-API-Key": ""}).status_code == 401
    assert client.post("/chat/stream", json={"message": "hi"}).status_code == 401


def test_health_check_stays_open_without_key():
    assert client.get("/health-check").status_code == 200
