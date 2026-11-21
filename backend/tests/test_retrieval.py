from langchain_core.documents import Document

from app.services.retrieval import rrf_fuse


def _doc(i: int) -> Document:
    return Document(page_content=f"doc {i}", metadata={"chunk_id": str(i)})


def test_rrf_prefers_docs_present_in_both_rankings():
    a = [_doc(1), _doc(2), _doc(3)]
    b = [_doc(3), _doc(4), _doc(1)]
    fused = rrf_fuse([a, b], k=3)
    assert [d.metadata["chunk_id"] for d in fused][:2] == ["1", "3"]


def test_rrf_respects_k():
    assert len(rrf_fuse([[_doc(i) for i in range(10)]], k=4)) == 4
