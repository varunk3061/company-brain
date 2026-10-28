"""Cross-encoder reranking of retrieved chunks, plus the low-confidence abstain check.

Retrieval (vector + graph) finds a wide pool of permitted chunks; a cross-encoder then reads
the question and each chunk together and scores how well the chunk answers it. Only chunks
that already passed the permission filter ever reach this module.

Providers (RERANK_PROVIDER):
    local   cross-encoder/ms-marco-MiniLM-L-6-v2 on CPU (default)
    nvidia  NVIDIA hosted reranker, falls back to local on any error
    none    reranking off: retrieval keeps its original vector-score order

Every score is a probability in [0, 1] (sigmoid of the model logit), so one threshold works.
If every provider fails, the caller keeps the original order and nothing is abstained on.
"""

import json
import logging
import math
import os
import threading
import urllib.request
from collections.abc import Callable

logger = logging.getLogger(__name__)

RERANK_PROVIDER = os.getenv("RERANK_PROVIDER", "local").strip().lower()

# How many retrieved candidates are scored, and how many reach the LLM.
RERANK_CANDIDATES = int(os.getenv("RERANK_CANDIDATES", "50"))
RERANK_TOP_N = int(os.getenv("RERANK_TOP_N", "6"))

# Abstain when the best chunk scores below this. Tune with `python -m scripts.tune_rerank`.
RERANK_MIN_SCORE = float(os.getenv("RERANK_MIN_SCORE", "0.02"))

LOCAL_RERANK_MODEL = os.getenv("LOCAL_RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_RERANK_MODEL = os.getenv("NVIDIA_RERANK_MODEL", "nvidia/llama-3.2-nv-rerankqa-1b-v2")
NVIDIA_RERANK_URL = os.getenv(
    "NVIDIA_RERANK_URL",
    "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-3_2-nv-rerankqa-1b-v2/reranking",
)
NVIDIA_RERANK_TIMEOUT_SECONDS = float(os.getenv("NVIDIA_RERANK_TIMEOUT_SECONDS", "10"))

# Loaded once per backend process, on first use (keeps startup and tests light).
_local_model = None
_local_model_lock = threading.Lock()


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value)) if value >= 0 else math.exp(value) / (1.0 + math.exp(value))


def _get_local_model():
    global _local_model

    if _local_model is None:
        with _local_model_lock:
            if _local_model is None:
                from sentence_transformers import CrossEncoder

                _local_model = CrossEncoder(LOCAL_RERANK_MODEL, device="cpu", max_length=512)

    return _local_model


def _score_local(question: str, texts: list[str]) -> list[float]:
    """Score with the local MiniLM cross-encoder; returns sigmoid probabilities."""

    import torch

    model = _get_local_model()
    pairs = [(question, text) for text in texts]

    # The activation keyword is `activation_fn` in sentence-transformers >= 4, `activation_fct` before.
    try:
        scores = model.predict(pairs, batch_size=32, show_progress_bar=False, activation_fn=torch.nn.Sigmoid())
    except TypeError:
        scores = model.predict(pairs, batch_size=32, show_progress_bar=False, activation_fct=torch.nn.Sigmoid())

    return [float(score) for score in scores]


def _score_nvidia(question: str, texts: list[str]) -> list[float]:
    """Score with the NVIDIA hosted reranker; returns sigmoid probabilities."""

    if not NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY is not configured.")

    body = json.dumps({
        "model": NVIDIA_RERANK_MODEL,
        "query": {"text": question},
        "passages": [{"text": text} for text in texts],
        "truncate": "END",
    }).encode("utf-8")

    request = urllib.request.Request(
        NVIDIA_RERANK_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=NVIDIA_RERANK_TIMEOUT_SECONDS) as response:
        rankings = json.loads(response.read().decode("utf-8"))["rankings"]

    scores = [0.0] * len(texts)
    for item in rankings:
        scores[int(item["index"])] = _sigmoid(float(item["logit"]))
    return scores


def _providers() -> list[tuple[str, Callable[[str, list[str]], list[float]]]]:
    if RERANK_PROVIDER == "nvidia":
        return [("nvidia", _score_nvidia), ("local", _score_local)]
    if RERANK_PROVIDER == "local":
        return [("local", _score_local)]
    return []


def rerank(question: str, chunks: list) -> list | None:
    """
    Return the chunks sorted by cross-encoder relevance, each with `rerank_score` and
    `rerank_provider` set. Returns None when reranking is off or every provider failed,
    so the caller can keep its existing ordering.
    """

    if not chunks:
        return []

    texts = [str(chunk.get("text") or "") for chunk in chunks]

    for name, score in _providers():
        try:
            scores = score(question, texts)
        except Exception as exc:
            logger.warning("Reranker '%s' failed: %s: %s", name, type(exc).__name__, exc)
            continue

        reranked = [
            {**chunk, "rerank_score": value, "rerank_provider": name}
            for chunk, value in zip(chunks, scores)
        ]
        reranked.sort(key=lambda chunk: chunk["rerank_score"], reverse=True)
        return reranked

    return None


def top_score(chunks: list) -> float | None:
    """Best rerank score among the chunks, or None if they were not reranked."""

    scores = [c["rerank_score"] for c in chunks if c.get("rerank_score") is not None]
    return max(scores) if scores else None


def is_low_confidence(chunks: list) -> bool:
    """True when the chunks were reranked and even the best one is below the threshold."""

    best = top_score(chunks)
    return best is not None and best < RERANK_MIN_SCORE


def audit_summary(chunks: list) -> dict | None:
    """Compact rerank details for the audit log (no chunk text)."""

    if top_score(chunks) is None:
        return None

    return {
        "provider": chunks[0].get("rerank_provider"),
        "top_score": round(top_score(chunks), 4),
        "threshold": RERANK_MIN_SCORE,
        "chunks": [
            {
                "chunk_uuid": c.get("chunk_uuid"),
                "document_uuid": c.get("document_uuid"),
                "page": c.get("page"),
                "score": round(c["rerank_score"], 4),
            }
            for c in chunks
        ],
    }
