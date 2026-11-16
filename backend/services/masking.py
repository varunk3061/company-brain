"""Permission-aware masking for Company Brain evidence and answers."""

import re

from services.access.policy import UserContext


# Always redact these values, regardless of the user's role.
SECRET_PATTERNS = [
    re.compile(
        r"(?i)\b(api[_ -]?key|password|passwd|secret|token)\b"
        r"(\s*[:=]\s*)([^\s,;]+)"
    ),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._\-~+/]+=*\b"),
    re.compile(r"(?i)\bsk-[a-z0-9]{16,}\b"),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----", re.DOTALL),
]

EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)

PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+91[-\s]?)?[6-9]\d{9}(?!\d)"
)

PAN_PATTERN = re.compile(
    r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
    re.IGNORECASE,
)

AADHAAR_PATTERN = re.compile(
    r"(?<!\d)\d{4}[-\s]?\d{4}[-\s]?\d{4}(?!\d)"
)

# Matches salary, bonus, CTC, payroll, etc., followed by an amount.
COMPENSATION_PATTERN = re.compile(
    r"(?i)\b("
    r"salary|bonus|ctc|compensation|payroll|annual\s+pay|monthly\s+pay"
    r")\b"
    r"(\s*(?:is|:|=|of)?\s*)"
    r"((?:₹|inr|rs\.?)\s?[\d,]+(?:\.\d+)?(?:\s*(?:lakh|lakhs|crore|k))?)"
)

# Matches bank-account labels and their numeric values.
BANK_ACCOUNT_PATTERN = re.compile(
    r"(?i)\b("
    r"bank\s+account(?:\s+number)?|account\s+number|a/c\s*(?:no|number)?"
    r")\b"
    r"(\s*(?:is|:|=|of)?\s*)"
    r"(\d{8,18})"
)

# Matches financial labels and their associated amounts.
FINANCIAL_VALUE_PATTERN = re.compile(
    r"(?i)\b("
    r"invoice\s+amount|budget|reimbursement|payment|amount\s+payable|"
    r"contract\s+value|outstanding\s+amount"
    r")\b"
    r"(\s*(?:is|:|=|of)?\s*)"
    r"((?:₹|inr|rs\.?)\s?[\d,]+(?:\.\d+)?(?:\s*(?:lakh|lakhs|crore|k))?)"
)


def _replace_with_label( #	Entire matched text
    text: str,
    pattern: re.Pattern,
    label: str,
) -> tuple[str, bool]:
    """Replace every matching value with a safe label."""

    masked_text, count = pattern.subn(label, text)
    return masked_text, count > 0


def _replace_labeled_value(
    text: str,
    pattern: re.Pattern,
    label: str,
) -> tuple[str, bool]:
    """Keep the field label but replace only its sensitive value."""

    def replacement(match: re.Match) -> str:
        return f"{match.group(1)}{match.group(2)}{label}"

    masked_text, count = pattern.subn(replacement, text)
    return masked_text, count > 0


def mask_text_for_user(
    text: str,
    ctx: UserContext,
):
    """
    Return text safe for the current user and a list of masked categories.

    Secrets are always masked. Other categories require an explicit permission.
    """

    masked_text = str(text or "")
    masked_categories: list[str] = []

    # Secrets must never be returned, even to privileged users.
    for pattern in SECRET_PATTERNS:
        masked_text, changed = _replace_with_label(masked_text,pattern,"[REDACTED_SECRET]",)
        if changed:
            masked_categories.append("secret")
    #here is not permission check for secrets, they are always masked
    # Employee API key: abc123 ==Employee [REDACTED_SECRET]

    if not ctx.has("sensitive.pii.read"):
        for pattern, label in [
            (EMAIL_PATTERN, "[REDACTED_EMAIL]"),
            (PHONE_PATTERN, "[REDACTED_PHONE]"),
            (PAN_PATTERN, "[REDACTED_ID]"),
            (AADHAAR_PATTERN, "[REDACTED_ID]"),
        ]:
            masked_text, changed = _replace_with_label(
                masked_text,
                pattern,
                label,
            )
            if changed:
                masked_categories.append("pii")

    if not ctx.has("sensitive.compensation.read"):
        masked_text, changed = _replace_labeled_value(
            masked_text,
            COMPENSATION_PATTERN,
            "[REDACTED_COMPENSATION]",
        )
        if changed:
            masked_categories.append("compensation")

    if not ctx.has("sensitive.financial.read"):
        for pattern, label in [
            (BANK_ACCOUNT_PATTERN, "[REDACTED_BANK_ACCOUNT]"),
            (FINANCIAL_VALUE_PATTERN, "[REDACTED_FINANCIAL_VALUE]"),
        ]:
            masked_text, changed = _replace_labeled_value(
                masked_text,
                pattern,
                label,
            )
            if changed:
                masked_categories.append("financial")

    # Preserve category order while removing duplicates.
    return masked_text, list(dict.fromkeys(masked_categories))


def mask_chunks_for_user(
    chunks: list[dict],
    ctx: UserContext,
) -> tuple[list[dict], list[str]]:
    """Copy and mask retrieved chunks before reranking or LLM generation."""

    safe_chunks: list[dict] = []
    all_categories: list[str] = []

    for chunk in chunks:
        safe_chunk = dict(chunk) #makes the shallow copy of the chunk, so that we can modify the copy without affecting the original
        safe_chunk["text"], categories = mask_text_for_user(str(chunk.get("text") or ""),ctx,) #it passes only the chunk text not whole chunk
        safe_chunks.append(safe_chunk)
        all_categories.extend(categories)

    return safe_chunks, list(dict.fromkeys(all_categories))


def mask_facts_for_user(
    facts: list[dict],
    ctx: UserContext,
) -> tuple[list[dict], list[str]]:
    """Copy and mask graph-fact values before LLM generation."""

    safe_facts: list[dict] = []
    all_categories: list[str] = []

    for fact in facts:
        safe_fact = dict(fact)

        for field in ("subject", "relation", "object"):
            safe_fact[field], categories = mask_text_for_user(
                str(fact.get(field) or ""),
                ctx,
            )
            #         safe_fact = {
            # "subject": "Rahul",
            # "relation": "HAS_EMAIL",
            # "object": "[REDACTED_EMAIL]",}
            all_categories.extend(categories)

        safe_facts.append(safe_fact)

    return safe_facts, list(dict.fromkeys(all_categories))