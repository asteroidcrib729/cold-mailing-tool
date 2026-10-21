# Live Testing 02: Working Flash-Lite Model and Desktop Confirmation

Date: 2026-10-20 (Asia/Karachi).

Status: `models/gemini-3.1-flash-lite` passed four real generation requests,
including three in the source desktop workflow at the default 30-second timeout.
This supersedes the generation-blocked status in [Live Testing 01](live-testing-01.md).
SMTP transmission, recipient receipt, installer live testing, broader semantic
evaluation, and production acceptance remain open. No email was sent.

## Scope and model choice

The owner supplied the project's Google AI Studio rate-limit screenshots and
requested tests of other models with appropriate limits. Testing was capped at
six additional generation requests; only five were needed. All contacts and
briefs were fictional. A refusing SMTP transport prevented email sending.

The screenshots show these nonzero limits for relevant text models. These are
project-specific observations from the owner's screenshots, not universal quotas
or results from a quota API. The visible usage numerator is distinct from the
allowed-limit denominator.

| Model | Screenshot RPM limit | Screenshot input TPM limit | This iteration |
| --- | --- | --- | --- |
| Gemini 3.1 Flash-Lite | 15 | 250,000 | Four requests succeeded; recommended for the current development setup. |
| Gemini 3.5 Flash-Lite | 15 | 250,000 | One request returned HTTP 504 at the 30-second deadline. |
| Gemini 2.5 Flash-Lite | 10 | 250,000 | Not tested after a suitable working model was found. |
| Gemini 3.6 Flash | 5 | 250,000 | Not tested after a suitable working model was found. |
| Gemini 3.8 Flash | 5 | 250,000 | Previous one-request trial returned HTTP 504; not repeated. |

Models showing zero quota, embedding/image/audio models, agents, and Live API
models were not candidates for this application's plain-text generation path.
Gemma's higher visible RPM alone does not establish compatibility with the current
structured-output adapter, so it was not selected over a working compatible model.

Google documents [Gemini 3.1 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite)
as supporting structured output and lightweight text tasks. Google's
[rate-limit documentation](https://ai.google.dev/gemini-api/docs/rate-limits)
explains that RPM, input TPM, and RPD are independent project-wide limits,
shared across API keys, and that capacity is not guaranteed. The supplied daily
quota graph is for a different selected model; it does not establish Flash-Lite's
daily allowance. Consult the active project's selected-model daily limit before
planning bulk generation.

## Observed generation requests

| Request | Model | Timeout | Result | Duration | Input / total tokens |
| --- | --- | --- | --- | --- | --- |
| Comparison 1 | `models/gemini-3.5-flash-lite` | 30 seconds | HTTP 504, `DEADLINE_EXCEEDED` | 29.933 seconds | Unavailable |
| Comparison 2 | `models/gemini-3.1-flash-lite` | 90 seconds, test override only | Valid draft saved, unapproved | 8.940 seconds | 127 / 188 |
| Desktop recipient 1 | `models/gemini-3.1-flash-lite` | 30 seconds | Valid draft saved, unapproved | 9.805 seconds | 145 / 206 |
| Desktop recipient 2 | `models/gemini-3.1-flash-lite` | 30 seconds | Valid draft saved, unapproved | 15.603 seconds | 145 / 207 |
| Desktop candidate | `models/gemini-3.1-flash-lite` | 30 seconds | Valid candidate; explicitly rejected without overwriting the draft | 9.316 seconds | 145 / 203 |

The model reported its version as `gemini-3.1-flash-lite` on every successful
request, with finish reason `STOP`. Responses passed the real adapter's JSON and
subject/body validation, campaign template rendering, and application persistence.
The comparison used one request per model, sequentially. The desktop used its
existing two-worker batch for two recipients and a later single candidate request.
Each SDK call had one attempt; no automatic retry or fallback was added.

The successful 30-second desktop requests show that the 90-second override is
not required for these observed successes. They do not explain every earlier
503/504 response, demonstrate that 3.5 Flash-Lite always fails, or establish a
capacity guarantee. This is a small functional test, not a comparative quality
benchmark or sustained quota/load test.

## Desktop and storage checks

The real PySide6 widgets, QThread worker, shared campaign engine, provider adapter,
and isolated SQLite profile were exercised with Qt's offscreen platform. This was
a source workflow test; no claim is made about visible rendering or installer
execution in this iteration.

All twelve recorded checks passed:

- Two recipients received their own saved subject/body drafts, initially unapproved.
- Each final body contained its own personalized greeting and the configured sign-off.
- Manual subject/body changes autosaved and did not modify the other recipient.
- The first edit immediately invalidated the previously approved revision.
- Turning autosave off retained changes locally until explicit manual save.
- A newly generated candidate could be rejected without replacing the current draft.
- The next candidate operation was blocked by the three-request profile budget
  before another provider request was made.
- SMTP had zero calls and the database had zero transport attempts.
- The API-key value was absent from the isolated database.
- Restart preserved the manual revision and its unapproved state.
- Restart preserved the autosave-off preference and the explicitly saved test model.
- Restart did not create or replay any send attempt.

Three completed generation admissions and four saved revisions were recorded in
the desktop profile. During batch generation, 796 GUI heartbeat ticks were observed
with a maximum gap of 36.95 ms. No guarded error dialog was raised. These observations
do not certify performance under sustained load, accessibility, fault recovery, or
every autosave conflict path.

All live helpers verified `.env` remained byte-for-byte unchanged. The key was used
only in memory; the desktop helper used an in-memory credential store, with no
OS-keyring writes. The model and autosave preferences above belong only to the
isolated test profile. The normal profile and the application's default timeout
were not changed. Private helpers, generated synthetic drafts, and safe metadata
remain ignored under `reports/live-testing-01/`; they are not committed.

## Recommended configuration and remaining controls

For the current project, select this exact model in the desktop's AI settings, or
set the ignored development `.env` entry to:

```dotenv
GENAI_MODEL=models/gemini-3.1-flash-lite
```

Launch with `uv --cache-dir .uv-cache run --locked cold-mailer-desktop --development`
to explicitly load that file, and enable Live access for an intended generation
operation. Changing model selection does not authorize any email transmission.
The testing instruction did not itself change the owner's persistent model choice.

For bulk generation, add a model-aware admission limiter covering shared RPM,
input-token estimates, and daily quota, plus provider `Retry-After` handling.
The application currently enforces bounded workers and persistent request-count
budgets; these do not implement a provider RPM/TPM quota governor. SMTP pacing and
jitter apply to sending and do not throttle AI generation. As an interim operating
limit for this 15-RPM project, serial requests spaced at least five seconds apart
provide RPM headroom, while input TPM, daily quota, and other project clients still
need separate accounting. Do not describe this as an enforced application setting.

Next acceptance work is a deliberately bounded SMTP test using fresh credentials,
one owned recipient, reviewed exact content, and an agreed send count. Record SMTP
acceptance separately from observed receipt. Signing, installer identity, clean-
machine installation, and upgrade testing remain their own release gates.

Only documentation changed in this iteration. Repository boundaries/document links,
diff whitespace, and the publishable source secret scan were checked. The preceding
source checkpoint's 189 offline tests and hosted Development/Security/CodeQL checks
passed; no new source behavior or dependency change required repeating that suite.
