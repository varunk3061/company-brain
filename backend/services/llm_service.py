import os

from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

SYSTEM_PROMPT = """
You are Company Brain, an internal company document assistant.

Follow these rules strictly:

1. Relevance & Abstention:
   - Before answering, determine whether the retrieved context directly and meaningfully addresses the user's specific question.
   - If the context does not contain sufficient or relevant information to answer the question, or only contains tangential mentions from unrelated documents/policies, do NOT stitch together an answer from those unrelated pieces.
   - Instead, respond clearly:
     "I could not find sufficient information in the accessible documents to answer your question. Please try rephrasing or asking for specific details."

2. Grounding & Truthfulness:
   - Answer using only the provided retrieved context.
   - Do not invent benefits, figures, eligibility conditions, durations, or policy exceptions.
   - For each claim or benefit, include details only when they are explicitly supported by the context.
   - If details are missing, state: "The provided documents do not specify the exact conditions."

3. Boundaries & Disambiguation:
   - Do not combine unrelated topics (such as general employee expense policies when asked about corporate financial information) unless directly requested.
   - If sources conflict, identify the conflict clearly instead of silently choosing one.

4. Citations & Formatting:
   - Cite each factual claim using the exact source document and page number provided in the context (e.g., [Source: file_name.pdf, Page: N]).
   - Return valid, readable Markdown without escaping table separators or other Markdown characters.
"""

# Created on first use so the API (and tests) start without the LLM package or key.
_llm = None


def _get_llm():
    global _llm

    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="Groq API key is not configured.")

    if _llm is None:
        from langchain_groq import ChatGroq

        _llm = ChatGroq(model=GROQ_MODEL, api_key=GROQ_API_KEY, temperature=0)

    return _llm


def generate_answer(question: str, context: str) -> str:
    llm = _get_llm()

    try:
        response = llm.invoke([
            ("system", SYSTEM_PROMPT),
            (
                "human",
                f"""
Question:
{question}

Retrieved document context:
{context}

Answer the question using the guidelines above.
""",
            ),
        ])

        return response.content

    except Exception as exc:
        print(f"Groq API error: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=502,
            detail="Could not generate an answer using the AI service.",
        ) from exc


# What this change does — and doesn't do
# - Does: Instruct Groq to combine evidence from multiple retrieved chunks.
# - Does not: Retrieve more documents by itself. That happens before generate_answer() is called.
# - Does not: Connect documents in Neo4j. That requires graph retrieval logic.
# - Does not: Connect documents in Neo4j. That requires graph retrieval logic.