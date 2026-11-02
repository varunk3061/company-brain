"""Test questions and compare generated answers/retrieved sources against expected samples.

Usage:
    # 1. Test using a JSON file of question/answer pairs:
    python -m scripts.eval_questions --file scripts/sample_questions.json

    # 2. Test as a specific user (tests their specific access permissions):
    python -m scripts.eval_questions --file scripts/sample_questions.json --email karan.joshi@nexora-tech.example

    # 3. Test retrieval only (fast, no LLM call/cost):
    python -m scripts.eval_questions --file scripts/sample_questions.json --retrieval-only

    # 4. Test a single ad-hoc question:
    python -m scripts.eval_questions -q "What is the notice period?" -a "30 days" -s "HR"
"""

import argparse
import json
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from database.connection import users_collection
from services import rerank_service
from services.llm_service import generate_answer, is_abstention
from services.retrieval_service import plan_retrieval, retrieve_graph_facts, retrieve_relevant_chunks
from utils.auth import build_user_context

# ANSI terminal colors
_TTY = sys.stdout.isatty()
GREEN, RED, YELLOW, BLUE, CYAN, BOLD, RESET = (
    ("\033[32m", "\033[31m", "\033[33m", "\033[34m", "\033[36m", "\033[1m", "\033[0m")
    if _TTY
    else ("", "", "", "", "", "", "")
)


def run_one_question(item: dict, ctx, retrieval_only: bool = False) -> dict:
    question = item.get("question", "").strip()
    expected_ans = item.get("expected_answer", "").strip()
    expected_src = item.get("expected_source", "").strip()

    if not question:
        return {"error": "Empty question"}

    t0 = time.perf_counter()

    # 1. Retrieval (Hybrid search + GraphDB facts)
    plan = plan_retrieval(question)
    chunks = retrieve_relevant_chunks(question=question, ctx=ctx, limit=10, plan=plan)
    facts = retrieve_graph_facts(plan, ctx)

    retrieval_time = time.perf_counter() - t0

    # Format retrieved sources
    retrieved_sources = []
    for c in chunks:
        src = c.get("source", "Unknown")
        p = c.get("page")
        retrieved_sources.append(f"{src} (p.{p})")

    for f in facts:
        src = f.get("source", "Unknown")
        p = f.get("page")
        retrieved_sources.append(f"{src} (p.{p}) [fact]")

    unique_sources = list(dict.fromkeys(retrieved_sources))

    # Source check
    source_match = True
    if expected_src:
        source_match = any(expected_src.lower() in s.lower() for s in unique_sources)

    if retrieval_only:
        return {
            "question": question,
            "route": plan.name,
            "chunks_count": len(chunks),
            "facts_count": len(facts),
            "sources": unique_sources[:4],
            "source_match": source_match,
            "expected_source": expected_src,
            "time_sec": round(retrieval_time, 2),
            "answer": None,
            "answer_match": None,
        }

    # 2. Answer Generation via LLM
    if not chunks and not facts:
        answer = "I could not find this information in the accessible documents."
    else:
        context_parts = [
            f"Source: {c.get('source', 'Unknown document')}\nPage: {c.get('page')}\nContent:\n{c.get('text', '')}"
            for c in chunks
        ]
        if facts:
            context_parts.append(
                "Knowledge-graph facts:\n"
                + "\n".join(f"- {f['subject']} {f['relation']} {f['object']} (Source: {f['source']}, Page: {f['page']})" for f in facts)
            )
        context = "\n\n---\n\n".join(context_parts)
        answer = generate_answer(question=question, context=context)

    total_time = time.perf_counter() - t0

    # Answer match check (loose keyword match)
    answer_match = True
    if expected_ans:
        answer_match = expected_ans.lower() in answer.lower()

    return {
        "question": question,
        "route": plan.name,
        "chunks_count": len(chunks),
        "facts_count": len(facts),
        "sources": unique_sources[:4],
        "source_match": source_match,
        "expected_source": expected_src,
        "answer": answer,
        "expected_answer": expected_ans,
        "answer_match": answer_match,
        "abstained": is_abstention(answer),
        "time_sec": round(total_time, 2),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", "-f", help="JSON file containing question/answer list")
    parser.add_argument("--email", "-e", default="aarav.mehta@nexora-tech.example", help="User email to run as (default: Aarav Mehta / Admin)")
    parser.add_argument("--retrieval-only", action="store_true", help="Only test retrieval without calling LLM")
    parser.add_argument("-q", "--question", help="Single question to test")
    parser.add_argument("-a", "--expected-answer", default="", help="Expected answer for single question")
    parser.add_argument("-s", "--expected-source", default="", help="Expected source name for single question")

    args = parser.parse_args()

    # Load questions
    items = []
    if args.file:
        if not os.path.exists(args.file):
            print(f"{RED}File not found: {args.file}{RESET}")
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            items = json.load(f)
    elif args.question:
        items = [{
            "question": args.question,
            "expected_answer": args.expected_answer,
            "expected_source": args.expected_source,
        }]
    else:
        # Default sample questions if no args
        default_file = os.path.join(os.path.dirname(__file__), "sample_questions.json")
        if os.path.exists(default_file):
            with open(default_file, "r", encoding="utf-8") as f:
                items = json.load(f)
        else:
            print(f"{YELLOW}No questions specified. Use --file <path> or -q 'question'{RESET}")
            sys.exit(1)

    # Load User Context
    user = users_collection.find_one({"email": args.email.strip().lower()})
    if not user:
        # Fallback to any active user if default email is missing
        user = users_collection.find_one({})
        if not user:
            print(f"{RED}No users found in database.{RESET}")
            sys.exit(1)
        print(f"{YELLOW}User {args.email} not found. Running as {user.get('email')}{RESET}")

    ctx = build_user_context(user)
    print(f"\n{BOLD}Running test with User:{RESET} {ctx.name} ({ctx.email}) | Dept: {ctx.department_code} | Role: {ctx.role_code}")
    print(f"{BOLD}Total Questions to Evaluate:{RESET} {len(items)}\n" + "=" * 75)

    passed_count = 0
    for idx, item in enumerate(items, start=1):
        q = item.get("question")
        print(f"\n{BOLD}[{idx}/{len(items)}] Q:{RESET} {q}")
        res = run_one_question(item, ctx, retrieval_only=args.retrieval_only)

        print(f"    {CYAN}Route:{RESET} {res['route']} | {CYAN}Chunks:{RESET} {res['chunks_count']} | {CYAN}Facts:{RESET} {res['facts_count']} | {CYAN}Time:{RESET} {res['time_sec']}s")
        print(f"    {CYAN}Top Sources:{RESET} {', '.join(res['sources']) if res['sources'] else 'None'}")

        # Check source match
        if res.get("expected_source"):
            src_status = f"{GREEN}PASS{RESET}" if res["source_match"] else f"{RED}FAIL (expected '{res['expected_source']}'){RESET}"
            print(f"    {CYAN}Source Match:{RESET} {src_status}")

        if not args.retrieval_only:
            ans = res.get("answer", "")
            print(f"    {CYAN}Generated Answer:{RESET}\n    {ans.strip()}")
            if res.get("expected_answer"):
                ans_status = f"{GREEN}PASS{RESET}" if res["answer_match"] else f"{YELLOW}DIFF (expected '{res['expected_answer']}'){RESET}"
                print(f"    {CYAN}Answer Validation:{RESET} {ans_status}")

        is_success = (res.get("source_match", True) and (args.retrieval_only or res.get("answer_match", True)))
        if is_success:
            passed_count += 1

    print("\n" + "=" * 75)
    print(f"{BOLD}Summary:{RESET} {passed_count}/{len(items)} passed validation.")


if __name__ == "__main__":
    main()
