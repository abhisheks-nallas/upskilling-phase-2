
from types import SimpleNamespace

import pytest

from rag import PROMPTS, Bm25, Retriever, ask, chunk_v1, chunk_v2, fuse, load_docs

WORDS = ["leave", "days", "laptop", "vpn", "approval", "salary", "refund", "probation", "bonus", "week"]


def fake_embed(texts):
    # counts a few keywords, so "similar" text gets a similar vector. No model download in tests
    return [[float(t.lower().count(w)) for w in WORDS] + [0.1] for t in texts]


DOCS = [
    {"source": "leave.md", "title": "Leave", "text": "# Leave\n\n## Annual\nYou get 18 days of leave every year.\n\n## Sick\nSick leave is 10 days."},
    {"source": "it.md", "title": "IT", "text": "# IT\n\n## Laptop\nYou get a laptop on day 1.\n\n## VPN\nInstall the vpn client from the catalogue."},
]


def test_chunk_v1_cuts_by_size():
    chunks = chunk_v1({"source": "a.md", "text": "x" * 1000}, size=400)
    assert [len(c["text"]) for c in chunks] == [400, 400, 200]


def test_chunk_v2_one_chunk_per_heading_with_title():
    chunks = chunk_v2(DOCS[0])
    assert len(chunks) == 2
    assert chunks[0]["text"].startswith("Leave - Annual\n")
    assert "18 days" in chunks[0]["text"] and "Sick leave" not in chunks[0]["text"]


def test_real_knowledge_base_loads_and_every_doc_has_sections():
    docs = load_docs()
    assert len(docs) >= 10
    assert all(len(chunk_v2(d)) >= 3 for d in docs)


def test_bm25_finds_the_matching_text():
    bm25 = Bm25(["annual leave days", "laptop and vpn", "salary date"])
    assert bm25.rank("vpn", 3) == [1]  # chunks without the word are left out
    assert bm25.rank("zzz", 3) == []


def test_fuse_prefers_items_found_by_both_searchers():
    assert fuse([[3, 1, 2], [2, 3]])[:2] == [3, 2]


def test_retriever_v2_returns_the_right_section():
    r = Retriever("v2", DOCS, fake_embed)
    hits = r.search("how many days of leave", k=1)
    assert hits[0]["source"] == "leave.md" and "18 days" in hits[0]["text"]


def test_retriever_v2_keyword_match_rescues_what_embeddings_miss():
    r = Retriever("v2", DOCS, lambda texts: [[1.0] * 11 for _ in texts])  # embeddings tell nothing, so only BM25 can help
    assert "vpn" in r.search("vpn", k=1)[0]["text"].lower()


def test_retriever_rejects_unknown_version_and_empty_docs():
    with pytest.raises(ValueError):
        Retriever("v9", DOCS, fake_embed)
    with pytest.raises(ValueError):
        Retriever("v1", [], fake_embed)


class FakeLLM:
    def __init__(self):
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return SimpleNamespace(content="18 days.")


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_ask_returns_answer_contexts_and_uses_the_versions_prompt(version):
    llm = FakeLLM()
    out = ask("how many days of leave", retriever=Retriever(version, DOCS, fake_embed), llm=llm)
    assert out["answer"] == "18 days." and out["version"] == version
    assert out["contexts"] and "leave.md" in out["sources"]
    assert llm.prompts[0].startswith(PROMPTS[version].split("\n")[0])
    assert "how many days of leave" in llm.prompts[0]
