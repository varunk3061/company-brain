# 0001 — Data Masking Policy

## Context

Company Brain already prevents users from retrieving documents they are not allowed to view. Some permitted documents can still contain sensitive values, such as personal contact details, compensation, financial values, or secrets. These values need field-level protection for both the website chat and MCP clients.

The policy must be enforced by the backend. Frontend-only masking is not sufficient because MCP clients and direct API callers could bypass it.

## Policy

Sensitive values are denied by default. A value is visible only when the authenticated user's current role includes the permission for that data category.

| Category | Examples | Default behaviour | Required permission |
| --- | --- | --- | --- |
| Secrets | Passwords, API keys, bearer tokens, private keys | Always redact | Never return |
| Personal data | Personal email addresses, phone numbers, PAN/Aadhaar-like IDs | Redact | `sensitive.pii.read` |
| Compensation | Salary, bonus, payroll values | Redact | `sensitive.compensation.read` |
| Financial data | Bank accounts, invoice amounts, budget amounts | Redact | `sensitive.financial.read` |
| Legal-sensitive data | Protected contract or legal values | Redact | `sensitive.legal.read` |

Redacted output uses explicit labels such as `[REDACTED_PHONE]`, `[REDACTED_COMPENSATION]`, and `[REDACTED_SECRET]`. The original sensitive value must never appear in the response or audit record.

## Options considered

1. Mask only in the frontend.
2. Mask only after the LLM generates an answer.
3. Mask permitted evidence in the backend before reranking and LLM generation, then mask the final answer again.

## Experiment

The implementation will compare the website API and MCP tool for the same user, document, and question. Tests will cover authorised and unauthorised users for each category.

## Numbers

Baseline and post-implementation results will be recorded here after the red-team tests are added.

| Metric | Baseline | Target |
| --- | --- | --- |
| Sensitive-value leaks in website responses | Not yet measured | 0 |
| Sensitive-value leaks in MCP responses | Not yet measured | 0 |
| Website/MCP masking-result mismatches | Not yet measured | 0 |

## Decision

Use backend, permission-aware dynamic masking. The shared Company Brain workflow will mask retrieved chunks and graph facts before the reranker and LLM see them. It will mask the final generated answer again before it is saved, audited, or returned.

Both the website route and the MCP tool call the shared workflow, so this single enforcement point applies the same policy to both entry points.

## What would change this decision

This decision should be revisited if document ingestion adds reliable, structured sensitivity labels for every field. In that case, metadata-driven masking can supplement the pattern-based implementation. The deny-by-default rule and backend enforcement remain required.
