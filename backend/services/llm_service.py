
import os

from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_MODEL = os.getenv(
    "NVIDIA_MODEL",
    "nvidia/nemotron-3.5-super-vl-120b-a12b",
)
NVIDIA_BASE_URL = os.getenv(
    "NVIDIA_BASE_URL",
    "https://integrate.api.nvidia.com/v1",
)

SYSTEM_PROMPT = """
You are Company Brain, an internal company document assistant.

Follow these rules strictly:

1. Relevance & Abstention:
   - Before answering, determine whether the retrieved context directly
     and meaningfully addresses the user's specific question.
   - If context is insufficient or irrelevant, do not combine unrelated
     information to construct an answer.
   - Respond:
     "I could not find sufficient information in the accessible
     documents to answer your question. Please try rephrasing
     or asking for specific details."

2. Grounding & Truthfulness:
   - Answer using only the provided retrieved context.
   - Do not invent benefits, figures, eligibility conditions,
     durations, or policy exceptions.
   - Include details only when explicitly supported by context.
   - If details are missing, state:
     "The provided documents do not specify the exact conditions."

3. Boundaries & Disambiguation:
   - Do not combine unrelated topics unless directly requested.
   - If sources conflict, identify the conflict clearly.

4. Citations & Formatting:
   - Cite each factual claim using the exact source document
     and page number provided in context.
   - Use valid, readable Markdown without escaping table
     separators or other Markdown characters.
"""

# Create models only when first needed.
_groq_llm = None
_nvidia_llm = None


def _get_groq_llm():
    global _groq_llm

    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    if _groq_llm is None:
        from langchain_groq import ChatGroq

        _groq_llm = ChatGroq(
            model=GROQ_MODEL,
            api_key=GROQ_API_KEY,
            temperature=0,
        )

    return _groq_llm


def _get_nvidia_llm():
    global _nvidia_llm

    if not NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY is not configured.")

    if _nvidia_llm is None:
        from langchain_openai import ChatOpenAI

        _nvidia_llm = ChatOpenAI(
        model=NVIDIA_MODEL,                  # nvidia/nemotron-3-super-120b-a12b
        api_key=NVIDIA_API_KEY,
        base_url=NVIDIA_BASE_URL,
        temperature=0.2,
        top_p=0.95,
        max_tokens=2048,
        timeout=60,
        max_retries=1,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )

    return _nvidia_llm


def generate_answer(question: str, context: str) -> str:
    messages = [
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
    ]

    # Try Groq first.
    try:
        response = _get_groq_llm().invoke(messages)
        return response.content

    except Exception as groq_error:
        print(
            "Groq failed; attempting NVIDIA fallback. "
            f"Error type: {type(groq_error).__name__}"
        )

    # Groq failed: try NVIDIA with the same question and context.
    try:
        response = _get_nvidia_llm().invoke(messages)
        print("Answer generated successfully using NVIDIA fallback.")
        return response.content

    # except Exception as nvidia_error:
    #     print(
    #         "NVIDIA fallback failed. "
    #         f"Error type: {type(nvidia_error).__name__}"
    #     )
    except Exception as nvidia_error:
        print(f"NVIDIA fallback failed: {type(nvidia_error).__name__}: {nvidia_error}")

        raise HTTPException(
            status_code=502,
            detail=(
                "Could not generate an answer. "
                "Both primary and fallback AI services failed."
            ),
        ) from nvidia_error
