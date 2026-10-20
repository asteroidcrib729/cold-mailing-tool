# Live Testing 01: Gemini Metadata and Generation Failure Handling

Date: 2026-10-20 (Asia/Karachi).

Historical record: [Live Testing 02](live-testing-02.md) supersedes the blocked
generation status below after four successful Gemini 3.1 Flash-Lite requests.
The original observations and incomplete assertions from this run remain unchanged.

Status: model metadata checks passed; all four generation requests failed with
HTTP 503/504. Successful live generation, editing of a real generated draft,
SMTP seed transmission, recipient receipt, and packaged-app live acceptance
remain open. No email was sent. This record continues [Plan 02](development-plan-02.md)
and [Execution 03](execution-03.md).

## Authorization and configuration

The owner requested live testing using a newly created Google AI Studio project,
`Cold-Mailing-Tool-App`, and a fresh key in the ignored root `.env`. The configured
model is `models/gemini-flash-latest`. After three failures, the owner explicitly
approved one synthetic request using `models/gemini-3.8-flash`, without editing
the configured model. That request also failed; further generation requests stopped.

Only synthetic contact data was used, with fictional names and `example.com`
addresses. SMTP was disabled and a refusing transport was injected. The new key
was read in memory for this authorized test, never printed, saved to SQLite,
copied into a report, or stored in the OS credential manager by these helpers.
Every live helper verified that `.env` remained byte-for-byte unchanged.

The actual local variable is the supported development alias `API_KEY`.
`Settings.load(development=True, network=True)` loads it; normal application
startup does not read `.env`. `GOOGLE_GENAI_API_KEY` remains the canonical variable.
The helpers checked that the selected key matched the file rather than an
inherited environment variable. Neither the variable name nor its value was changed.

The Google SDK accepts the `models/` resource prefix; the successful metadata
lookup confirmed the exact configured resource and `generateContent` capability.
The alias is a moving model selection, as described in Google's
[model naming documentation](https://ai.google.dev/gemini-api/docs/models).
No automatic fallback or permanent model change was introduced.

## Observed requests

Two metadata operations succeeded: one lookup of the configured model and one
bounded model-list page. These establish authentication for those endpoints and
model discovery, not successful generation, available billing, or remaining quota.

| Operation | Requested model | Result | Observed duration |
| --- | --- | --- | --- |
| Model metadata lookup | `models/gemini-flash-latest` | Success; resource name and generation capability returned | 1.774 seconds |
| Desktop batch, recipient 1 | `models/gemini-flash-latest` | HTTP 503, SDK `ServerError` | 4.019 seconds |
| Desktop batch, recipient 2 | `models/gemini-flash-latest` | HTTP 504, SDK `ServerError` | 29.355 seconds |
| Explicit serial retry | `models/gemini-flash-latest` | HTTP 503, SDK `ServerError` | 5.290 seconds |
| Model-list metadata page | Not a generation request | Success; stable Flash resources included `models/gemini-3.8-flash` | Not recorded |
| Owner-approved stable-model trial | `models/gemini-3.8-flash` | HTTP 504, SDK `ServerError` | 29.245 seconds |

The original alias profile allowed three admissions in total; failures count
conservatively toward its rolling budget. The stable trial used a separate
synthetic profile with a one-request cap, reflecting the separate owner approval.
The existing 30-second request timeout, one SDK attempt, structured JSON output,
and 1,000 output-token ceiling were retained. The explicit serial retry was a
separate operation, not an automatic retry loop.

The responses do not establish an invalid key, invalid model syntax, quota
exhaustion, or a global outage. Google's
[troubleshooting guide](https://ai.google.dev/gemini-api/docs/troubleshooting)
describes provider error handling; the underlying cause of these particular
failures remains unverified. No generated model-version or usage metadata was
available because no generation request succeeded.

## Desktop and persistence observations

The initial test exercised the source PySide6 window, its background QThread
worker, the shared campaign service, the real AI adapter, and isolated SQLite
storage. During the failed batch the GUI heartbeat ran 1,527 times with a maximum
observed gap of 57.62 ms. The event loop remained active in this run; this is not
a general frame-time, load, or accessibility certification.

After the serial retry, the alias profile contained three failed generation
admissions, zero generated bodies, no approvals, and no SMTP attempts. The stable
profile contained one failed admission with the same empty, unapproved state.
The helpers checked that neither database contained the API-key value. Provider
failure text was not substituted for message content.

The planned live journey stopped at generation. Its later editing, autosave,
candidate acceptance, approval invalidation, and restart assertions were not
reached and are not reported as live passes. Offline coverage of these features
remains separate evidence. The pre-existing EXE/MSIX artifacts were not rebuilt or
live-tested in this iteration.

Private helpers, redacted metadata, and isolated profiles are retained under the
ignored `reports/live-testing-01/` directory. Reports record status codes, timings,
and check results, without raw provider exceptions or credential values. This
directory is not part of the published source or release payload.

## Improvements made from the observations

Previously the generation adapter collapsed provider failures into a generic
message. A typed `GenerationFailure` now maps validated integer HTTP codes to
fixed diagnostic hints for request configuration, access, billing, missing models,
quota, timeouts, and temporary service errors. Unknown or malformed status codes
receive a generic safe message. Raw exception text, request URLs, and response
bodies never enter those diagnostics.

Both serial and parallel batch generation retain these safe messages in the
operation log. Failed calls continue to count against budgets and leave content
and approval state untouched. There are no new retries or model fallbacks.

Regression tests exercise 14 status-code cases and serial/parallel campaign
failure paths. They verify fixed hints, response-text exclusion, unchanged model
selection, one SDK attempt, failed request journaling, empty unapproved drafts,
and zero transport history.

The full source verifier passed **189 offline tests**. Ruff, formatting, Pyrefly,
repository/documentation boundaries, actionlint, overall/critical coverage gates,
and the publishable source Gitleaks scan passed. Bandit over `src` and `scripts`
reported zero findings with existing narrowly documented exclusions retained.
No dependency or native-runtime vulnerability audit was repeated for this scoped
change; the existing SQLite WAL prerequisite remains open.

## Next live acceptance steps

1. Review the Google project quota/billing and service status without disclosing
   credentials. At a later explicitly bounded trial, retry one synthetic draft.
   If deadlines recur, review model latency and the application's timeout policy
   before changing settings. Preserve the current model preference unless the
   owner selects another one.
2. Once generation succeeds, finish the real draft journey: distinct recipients,
   manual subject/body customization, autosave on/off, candidate review, approval
   invalidation, restart recovery, and history checks. Do not count the current
   negative-path observations as passing those assertions.
3. For SMTP testing, choose the provider/host, port, TLS mode, username/sender,
   one owned recipient mailbox, and a strict send-count limit. Enter the fresh
   SMTP/app password through the application's hidden credential field, never in
   chat or a committed file. Confirm the exact reviewed message and recipient
   before any send. No credentials or recipients for this step have been supplied.
4. Record SMTP acceptance separately from the recipient's observed receipt and
   inbox placement. Compare exact saved subject/body/sender/recipient/timestamps
   with the reviewed message; verify that repeating a completed run cannot replay it.
5. Repeat acceptance on installer artifacts built from the reviewed source and
   complete the separate signing, clean-machine, upgrade, and release gates.

The owner also confirmed submission of the [GitHub Support request](github-support-request-01.md).
That is not evidence that GitHub has removed cached historical commits; support
resolution remains an external follow-up.
