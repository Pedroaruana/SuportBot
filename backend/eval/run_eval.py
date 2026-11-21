"""
Avaliação do RAG. Uso (a partir de backend/, com GEMINI_API_KEY no .env):

    python -m eval.run_eval              # retrieval + respostas
    python -m eval.run_eval --no-answers # só retrieval (não gasta tokens do LLM)

Usa um índice isolado em ./data/eval, sem tocar nos documentos reais.

Métricas:
  hit@1/hit@k o trecho com a evidência esperada está entre os k recuperados
  MRR        média de 1/posição da primeira evidência
  keywords   a resposta contém as palavras esperadas
  citation   a resposta cita ao menos um trecho no formato [n]
  recusa     perguntas fora do escopo recebem fallback ou "não encontrei"
Compara a busca vetorial pura com a híbrida (vetorial + BM25).
"""

import argparse
import json
import re
import shutil
import time
from pathlib import Path

from app.core.config import settings

EVAL_DIR = Path("./data/eval")
settings.chroma_persist_dir = str(EVAL_DIR / "chroma")
settings.sqlite_path = str(EVAL_DIR / "history.db")
# Chunks pequenos: o corpus de teste e curto, e com chunks grandes o k cobriria quase tudo
settings.chunk_size = 300
settings.chunk_overlap = 50

from app.services import ingestor, rag, retrieval  # noqa: E402
from app.services.store import get_vector_store, reset_store_cache  # noqa: E402

from eval.corpus import DOCS  # noqa: E402


def _build_pdf(text: str) -> bytes:
    import fitz

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_textbox(fitz.Rect(50, 50, 550, 780), text, fontsize=11)
    data = pdf.tobytes()
    pdf.close()
    return data


def _first_hit_rank(chunks: list[str], evidence: str) -> int | None:
    needle = evidence.lower()
    for i, text in enumerate(chunks, 1):
        if needle in re.sub(r"\s+", " ", text.lower()):
            return i
    return None


def _summarize(ranks: list[int | None], k: int) -> tuple[float, float]:
    n = len(ranks) or 1
    hit = sum(1 for r in ranks if r is not None and r <= k) / n
    mrr = sum(1 / r for r in ranks if r is not None) / n
    return hit, mrr


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-answers", action="store_true")
    parser.add_argument("--delay", type=float, default=1.0, help="pausa entre chamadas ao LLM (limite do plano gratuito)")
    args = parser.parse_args()

    if EVAL_DIR.exists():
        shutil.rmtree(EVAL_DIR)
    reset_store_cache()
    retrieval.invalidate_bm25()

    for name, text in DOCS.items():
        print(f"indexando {name}: {ingestor.ingest_pdf(_build_pdf(text), name)}")

    dataset = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))
    answerable = [q for q in dataset if q["answerable"]]
    k = settings.retriever_k
    store = get_vector_store()

    vector_ranks: list[int | None] = []
    hybrid_ranks: list[int | None] = []
    for q in answerable:
        vec_docs = store.similarity_search(q["question"], k=k)
        vector_ranks.append(_first_hit_rank([d.page_content for d in vec_docs], q["evidence"]))
        hits, _ = retrieval.retrieve(q["question"])
        hybrid_ranks.append(_first_hit_rank([h.doc.page_content for h in hits], q["evidence"]))

    v_hit, v_mrr = _summarize(vector_ranks, k)
    h_hit, h_mrr = _summarize(hybrid_ranks, k)
    v_hit1, _ = _summarize(vector_ranks, 1)
    h_hit1, _ = _summarize(hybrid_ranks, 1)
    lines = [
        f"## Retrieval ({len(answerable)} perguntas, k={k})",
        "",
        f"| Busca | hit@1 | hit@{k} | MRR |",
        "|---|---|---|---|",
        f"| Vetorial | {v_hit1:.2f} | {v_hit:.2f} | {v_mrr:.2f} |",
        f"| Híbrida (vetorial + BM25) | {h_hit1:.2f} | {h_hit:.2f} | {h_mrr:.2f} |",
    ]

    if not args.no_answers:
        kw_ok = cite_ok = fb_ok = 0
        out_of_scope = [q for q in dataset if not q["answerable"]]
        for q in dataset:
            result = rag.ask(q["question"], session_id=f"eval-{abs(hash(q['question']))}")
            if q["answerable"]:
                answer = result["answer"].lower()
                kw_ok += all(w.lower() in answer for w in q["keywords"]) and not result["fallback"]
                cite_ok += bool(re.search(r"\[\d+\]", result["answer"]))
            else:
                fb_ok += result["fallback"] or "não encontrei" in result["answer"].lower()
            time.sleep(args.delay)
        lines += [
            "",
            "## Respostas",
            "",
            "| Métrica | Resultado |",
            "|---|---|",
            f"| Palavras esperadas na resposta | {kw_ok}/{len(answerable)} |",
            f"| Resposta com citação [n] | {cite_ok}/{len(answerable)} |",
            f"| Recusa em perguntas fora do escopo (fallback ou o modelo admite que não sabe) | {fb_ok}/{len(out_of_scope)} |",
        ]

    report = "\n".join(lines)
    print("\n" + report)
    (Path(__file__).parent / "results.md").write_text(report + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
