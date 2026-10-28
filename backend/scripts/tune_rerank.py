"""Print the route, graph facts and rerank scores for real questions (test the router, tune RERANK_MIN_SCORE).

    python -m scripts.tune_rerank --email dev@nexora.com "What is the notice period?" "Who won the 1998 World Cup?"

Retrieval runs as that user (same permission filter as the chat) and the LLM is not called.
Ask a few questions the documents DO answer and a few they don't: set RERANK_MIN_SCORE in
.env between the lowest "answerable" top score and the highest "unanswerable" one.
"""

import argparse

from dotenv import load_dotenv

load_dotenv()

from database.connection import users_collection
from services import rerank_service
from services.retrieval_service import plan_retrieval, retrieve_graph_facts, retrieve_relevant_chunks
from utils.auth import build_user_context


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True, help="Run retrieval as this user")
    parser.add_argument("questions", nargs="+")
    args = parser.parse_args()

    if rerank_service.RERANK_PROVIDER == "none":
        print("Note: RERANK_PROVIDER is 'none', so no rerank scores will be shown.\n")

    user = users_collection.find_one({"email": args.email.strip().lower()})
    if not user:
        raise SystemExit(f"No user with email {args.email}")

    ctx = build_user_context(user)
    threshold = rerank_service.RERANK_MIN_SCORE
    print(f"Provider: {rerank_service.RERANK_PROVIDER}   current RERANK_MIN_SCORE: {threshold}\n")

    for question in args.questions:
        plan = plan_retrieval(question)
        chunks = retrieve_relevant_chunks(question=question, ctx=ctx, limit=10, plan=plan)
        facts = retrieve_graph_facts(plan, ctx)
        best = rerank_service.top_score(chunks)

        if not chunks and not facts:
            verdict = "no permitted chunks"
        elif facts:
            verdict = "answer (graph facts found)"
        elif best is None:
            verdict = "reranker unavailable (original order used)"
        else:
            verdict = "ABSTAIN" if best < threshold else "answer"

        print(f"Q: {question}")
        print(f"   route: {plan.name}   entities: {list(plan.entity_keys) or '-'}")
        for fact in facts:
            print(f"   fact: {fact['subject']} {fact['relation']} {fact['object']}  ({fact['source']} p.{fact['page']})")
        print(f"   top score: {best if best is None else round(best, 4)}  ->  {verdict}")
        for chunk in chunks:
            score = chunk.get("rerank_score")
            print(f"   {score if score is None else round(score, 4):>8}  {chunk.get('source')}  p.{chunk.get('page')}")
        print()


if __name__ == "__main__":
    main()
