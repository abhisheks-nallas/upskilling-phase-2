import os

import pytest

# Set before main.py is imported, because main loads .env and load_dotenv won't override what's already set.
# Without this, tests would send traces to the real LangSmith project.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGFUSE_TRACING_ENABLED"] = "false"  # same for Langfuse, tests must not create real traces


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
