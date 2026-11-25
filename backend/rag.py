
import math
import re
import uuid
from collections import Counter
from functools import lru_cache
from pathlib import Path

import chromadb
from langfuse import get_client, observe, propagate_attributes

# Two versions of the same pipeline, so we can measure what the changes buy us (see tools/rag_eval.py):
#   v1 = the naive baseline: fixed-size chunks, vector search only, a plain prompt
#   v2 = chunks follow the document headings, vector + keyword search merged, a stricter prompt
KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
CHUNK_SIZE = 400   # v1 chunk size in characters
CANDIDATES = 8     # v2: how many results each searcher gives before we merge them

PROMPTS = {
    "v1": "Answer the question using the context.\n\nContext:\n{context}\n\nQuestion: {question}",
    "v2": (
        "You are Onboarding Buddy, answering a new joiner's question.\n"
        "Answer ONLY from the context below, in 1 to 3 short sentences. Quote the exact numbers, days, amounts and times.\n"
        "If the context does not contain the answer, say you don't know and suggest asking HR.\n\n"
        "Context:\n{context}\n\nQuestion: {question}"
    ),
}


def load_docs(folder:Path = KNOWLEDGE_DIR) -> list[dict]:
    return [
        {"source": p.name, "title": p.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip(), "text": p.read_text(encoding="utf-8")}
        for p in sorted(Path(folder).glob("*.md"))
    ]


def chunk_v1(doc:dict, size:int = CHUNK_SIZE) -> list[dict]:
    # naive on purpose: cuts every `size` characters, even in the middle of a sentence. No overlap
    text = doc["text"]
    return [{"text": text[i:i + size].strip(), "source": doc["source"]} for i in range(0, len(text), size) if text[i:i + size].strip()]


def chunk_v2(doc:dict) -> list[dict]:
    # one chunk per "## " section. The doc title and heading go in front so the chunk makes sense on its own
    chunks = []
    for section in re.split(r"^## ", doc["text"], flags=re.M)[1:]:
        heading, _, body = section.partition("\n")
        chunks.append({"text": f"{doc['title']} - {heading.strip()}\n{body.strip()}", "source": doc["source"]})
    return chunks


def tokenize(text:str) -> list[str]:
    return re.findall(r"\w+", text.lower())


class Bm25:
    """Small keyword search (BM25), so v2 doesn't need another library."""
    def __init__(self, texts:list[str], k1:float = 1.5, b:float = 0.75):
        self.docs = [tokenize(t) for t in texts]
        self.k1, self.b = k1, b
        self.avg_len = sum(len(d) for d in self.docs) / len(self.docs)
        n = len(self.docs)
        counts = Counter(w for d in self.docs for w in set(d))
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in counts.items()}

    def rank(self, query:str, n:int) -> list[int]:
        scores = []
        for doc in self.docs:
            freq = Counter(doc)
            score = 0.0
            for w in set(tokenize(query)):
                if w in freq:
                    score += self.idf[w] * freq[w] * (self.k1 + 1) / (freq[w] + self.k1 * (1 - self.b + self.b * len(doc) / self.avg_len))
            scores.append(score)
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [i for i in order if scores[i] > 0][:n]


def fuse(rankings:list[list[int]], k:int = 60) -> list[int]:
    """Reciprocal rank fusion: merges several ranked lists. Items ranked high in any list float to the top."""
    score = Counter()
    for ranking in rankings:
        for pos, i in enumerate(ranking):
            score[i] += 1 / (k + pos + 1)
    return [i for i, _ in score.most_common()]


def default_embedder():
    # Chroma's built-in small model (MiniLM via onnx). Runs on CPU, no API key, no torch
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    return DefaultEmbeddingFunction()


class Retriever:
    def __init__(self, version:str = "v2", docs:list[dict] | None = None, embedding_function=None):
        if version not in PROMPTS:
            raise ValueError(f"Unknown RAG version '{version}'. Use 'v1' or 'v2'.")
        self.version = version
        chunker = chunk_v1 if version == "v1" else chunk_v2
        self.chunks = [c for d in (docs if docs is not None else load_docs()) for c in chunker(d)]
        if not self.chunks:
            raise ValueError("No documents to search. Put .md files in backend/knowledge.")
        self.embed_fn = embedding_function or default_embedder()
        # in-memory index, rebuilt at start up. 10 small docs take a second or two, so no database to look after
        self.collection = chromadb.Client().create_collection(f"kb-{version}-{uuid.uuid4().hex[:8]}")
        self.collection.add(ids=[str(i) for i in range(len(self.chunks))], documents=[c["text"] for c in self.chunks], embeddings=self.embed([c["text"] for c in self.chunks]))
        self.bm25 = Bm25([c["text"] for c in self.chunks])

    def embed(self, texts:list[str]) -> list[list[float]]:
        return [[float(x) for x in v] for v in self.embed_fn(texts)]

    @observe(name="retrieval", as_type="retriever", capture_input=False)
    def search(self, question:str, k:int = 3) -> list[dict]:
        get_client().update_current_span(input=question, metadata={"rag_version": self.version})
        n = min(k if self.version == "v1" else CANDIDATES, len(self.chunks))
        hit = self.collection.query(query_embeddings=self.embed([question]), n_results=n)
        by_meaning = [int(i) for i in hit["ids"][0]]
        if self.version == "v1":
            order = by_meaning[:k]
        else:
            order = fuse([by_meaning, self.bm25.rank(question, n)])[:k]
        return [self.chunks[i] for i in order]


@lru_cache(maxsize=2)
def get_retriever(version:str = "v2") -> Retriever:
    return Retriever(version)


@observe(name="generation", as_type="generation", capture_input=False)
def generate(llm, prompt:str) -> str:
    reply = llm.invoke(prompt)
    text = reply.content
    usage = getattr(reply, "usage_metadata", None)   # token counts, so Langfuse can show tokens and cost per query
    tokens = {"input": usage.get("input_tokens", 0), "output": usage.get("output_tokens", 0)} if isinstance(usage, dict) else None
    get_client().update_current_generation(input=prompt, output=text, usage_details=tokens, model=str(getattr(llm, "model", "") or getattr(llm, "model_name", "")))
    return text


@observe(name="rag-query", capture_input=False, capture_output=False)  # the arguments hold big objects, so we log the question ourselves
def ask(question:str, version:str = "v2", retriever:Retriever | None = None, llm=None, k:int = 3) -> dict:
    """Answer one question. Returns the answer, the passages it was based on and the Langfuse trace id."""
    get_client().update_current_span(input=question)
    if llm is None:
        from plan_graph import make_llm  # imported here so the retrieval code doesn't need the LLM libraries
        llm = make_llm()
    retriever = retriever or get_retriever(version)
    version = retriever.version
    with propagate_attributes(tags=[f"rag-{version}"], metadata={"rag_version": version}):
        hits = retriever.search(question, k)
        context = "\n\n".join(h["text"] for h in hits)
        answer = generate(llm, PROMPTS[retriever.version].format(context=context, question=question))
    get_client().update_current_span(output=answer)
    return {
        "question": question,
        "answer": answer,
        "contexts": [h["text"] for h in hits],
        "sources": sorted({h["source"] for h in hits}),
        "version": retriever.version,
        "trace_id": get_client().get_current_trace_id(),
    }
