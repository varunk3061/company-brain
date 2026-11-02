"""End-to-end smoke test against a running backend: employee login -> ask a question -> get an answer.

    cd backend
    python -m scripts.smoke_test_chat --email ravi@company.com
    python -m scripts.smoke_test_chat --email ravi@company.com -q "What is the leave policy?" -q "How many days carry over?"
    python -m scripts.smoke_test_chat --email ravi@company.com --keep        # keep the test conversation

The password is read from --password, else the SMOKE_PASSWORD env var, else asked for (hidden).
Uses only the HTTP API (no database access), so it tests exactly what the browser does.
The questions are sent in ONE conversation, so the follow-up path (existing conversation_id) is tested too.
By default the test conversation is deleted at the end.

Exit code: 0 = every question got a real answer, 1 = something failed or no real answer was given.
"""

# Logs in as an employee, asks questions like the chat page does, and says whether a real answer came back.

import argparse
import getpass
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_QUESTION = "What is the company leave policy?"

# Reply texts from the backend, and what each one means (see routes/rag_routes.py and services/llm_service.py).
VERDICTS = [
    ("i could not find this information in the accessible documents", "NO_CHUNKS",
     "Refused before the LLM: no permitted chunks found, or best rerank score below RERANK_MIN_SCORE."),
    ("i could not find sufficient information", "LLM_ABSTAINED",
     "The LLM was called but judged the retrieved chunks insufficient."),
    ("no answer was returned", "EMPTY",
     "The LLM returned empty text."),
]

# ANSI colours, turned off when the output is not a terminal.
_TTY = sys.stdout.isatty()
GREEN, RED, YELLOW, DIM, RESET = (("\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m") if _TTY
                                  else ("", "", "", "", ""))


class ApiError(Exception):
    def __init__(self, status, detail):
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


def call(base_url, method, path, body=None, token=None, timeout=180):
    """Send one JSON request; return (data, seconds). Raises ApiError on a non-2xx response."""

    headers = {"Accept": "application/json"}
    data = None

    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")

    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(f"{base_url}{path}", data=data, method=method, headers=headers)
    started = time.perf_counter()

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return (json.loads(raw) if raw else {}), time.perf_counter() - started

    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(raw).get("detail", raw)
        except (ValueError, AttributeError):
            detail = raw
        raise ApiError(exc.code, detail) from None

    except urllib.error.URLError as exc:
        raise ApiError(0, f"Cannot reach {base_url} ({exc.reason}). Is uvicorn running?") from None


def classify(answer):
    text = (answer or "").strip().lower()

    if not text:
        return "EMPTY", "The LLM returned empty text."

    for prefix, verdict, meaning in VERDICTS:
        if text.startswith(prefix):
            return verdict, meaning

    return "ANSWERED", "Real answer from the documents."


def step(label, ok, extra=""):
    mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
    print(f"[{mark}] {label}" + (f"  {DIM}{extra}{RESET}" if extra else ""))


def main():
    parser = argparse.ArgumentParser(description="Smoke test: employee login -> ask -> answer.")
    parser.add_argument("--email", required=True, help="Employee email to log in with.")
    parser.add_argument("--password", help="Password (else SMOKE_PASSWORD env var, else prompted).")
    parser.add_argument("-q", "--question", action="append",
                        help="Question to ask; repeat for follow-ups in the same conversation.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Backend URL (default {DEFAULT_BASE_URL}).")
    parser.add_argument("--keep", action="store_true", help="Keep the test conversation instead of deleting it.")
    parser.add_argument("--show-answer", type=int, default=600,
                        help="Characters of each answer to print (0 = all).")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    questions = args.question or [DEFAULT_QUESTION]
    password = args.password or os.getenv("SMOKE_PASSWORD") or getpass.getpass(f"Password for {args.email}: ")

    failures = 0
    print(f"Backend: {base_url}\n")

    # 1. Login
    try:
        login, seconds = call(base_url, "POST", "/auth/login", {"email": args.email, "password": password})
    except ApiError as exc:
        step("Login", False, str(exc))
        return 1

    token = login.get("access_token")
    user = login.get("user") or {}
    step("Login", bool(token), f"{seconds:.1f}s")

    if not token:
        print("  No access_token in the login response.")
        return 1

    print(f"  {user.get('name')} | dept {user.get('department_code')} | role {user.get('role_code')}"
          f" | clearance {user.get('clearance')}")

    # 2. Token works (/auth/me)
    try:
        me, seconds = call(base_url, "GET", "/auth/me", token=token)
        step("Token accepted (/auth/me)", me.get("user_uuid") == user.get("user_uuid"), f"{seconds:.1f}s")
    except ApiError as exc:
        step("Token accepted (/auth/me)", False, str(exc))
        return 1

    # 3. Ask the questions in one conversation
    conversation_id = None

    for number, question in enumerate(questions, start=1):
        label = f"Question {number}" + (" (follow-up)" if conversation_id else "")
        print(f"\n{label}: {question}")

        try:
            reply, seconds = call(base_url, "POST", "/api/rag/ask",
                                  {"question": question, "conversation_id": conversation_id}, token=token)
        except ApiError as exc:
            step(f"{label} answered", False, str(exc))
            failures += 1
            continue

        conversation_id = reply.get("conversation_id") or conversation_id
        answer = reply.get("answer") or ""
        sources = reply.get("sources") or []
        verdict, meaning = classify(answer)
        answered = verdict == "ANSWERED"

        step(f"{label} answered", answered, f"{seconds:.1f}s | {verdict}")

        if not answered:
            print(f"  {YELLOW}{meaning}{RESET}")
            failures += 1

        shown = answer if args.show_answer == 0 else answer[:args.show_answer]
        print("  Answer:")
        for line in (shown or "(empty)").splitlines():
            print(f"    {line}")
        if args.show_answer and len(answer) > args.show_answer:
            print(f"    {DIM}... ({len(answer) - args.show_answer} more characters){RESET}")

        if sources:
            print("  Sources:")
            for source in sources:
                print(f"    - {source.get('source')} (page {source.get('page')})")
        elif answered:
            print(f"  {YELLOW}Answered but cited no sources.{RESET}")

    # 4. The conversation was saved and holds every turn
    if conversation_id:
        try:
            saved, _ = call(base_url, "GET", f"/api/chat/conversations/{conversation_id}", token=token)
            count = len(saved.get("messages") or [])
            ok = count == 2 * len(questions)
            step("Conversation saved in history", ok, f"{count} messages, expected {2 * len(questions)}")
            failures += 0 if ok else 1
        except ApiError as exc:
            step("Conversation saved in history", False, str(exc))
            failures += 1

        # 5. Clean up
        if args.keep:
            print(f"\nKept conversation {conversation_id}")
        else:
            try:
                call(base_url, "DELETE", f"/api/chat/conversations/{conversation_id}", token=token)
                print(f"\n{DIM}Test conversation deleted (use --keep to keep it).{RESET}")
            except ApiError as exc:
                print(f"\n{YELLOW}Could not delete test conversation: {exc}{RESET}")

    print()
    if failures:
        print(f"{RED}{failures} check(s) failed.{RESET} If it says EMPTY or HTTP 502, check the uvicorn console "
              "for the 'NVIDIA ...' / 'Groq ...' log lines.")
        return 1

    print(f"{GREEN}All checks passed.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
