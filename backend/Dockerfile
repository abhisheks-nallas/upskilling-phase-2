
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# download the small embedding model now, so the first question doesn't wait for it
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction; DefaultEmbeddingFunction()(['warm up'])"
COPY main.py mcp_docs_server.py guardrails.py onboarding_tools.py plan_graph.py rag.py ./
COPY knowledge ./knowledge
# .env is mounted at run time, never baked into the image
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
