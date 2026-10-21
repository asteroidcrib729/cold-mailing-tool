# Cold Mailer

I am rebuilding this project as a local Windows desktop campaign workbench using
Python 3.14, PySide6 Widgets, SQLite, OS credential storage, and `uv`. Application
code lives in the installable `src/cold_mailer/` package. My
[Plan 01](development-plans/development-plan-01.md) is complete as the foundation
phase. My active [Plan 02](development-plans/development-plan-02.md) contains new
feature requirements and all transferred unfinished work. The
[first execution record](development-plans/execution-01.md) preserves baseline
evidence. [Execution 03](development-plans/execution-03.md) tracks the current
implementation and remaining acceptance work, including the now-authorized
[additional features](development-plans/features-and-improvements.md).
The account scope is now governed by [Plan 03](development-plans/development-plan-03.md):
users must explicitly sign in with a personal Gmail or Microsoft Outlook account.
See the [account setup guide](development-plans/personal-account-setup.md) and
[Execution 04](development-plans/execution-04.md) for implementation and live-verification limits.

## Repository structure

```text
src/cold_mailer/
    domain/          # Entities, validation, outcomes, and provider interfaces
    application/     # Shared campaign orchestration
    infrastructure/  # SQLite, OAuth accounts/mail, credentials, AI, contacts, templates, DNS
    ui/              # PySide6 window, table models, and workers
    cli.py           # CLI commands
    bootstrap.py     # Profile ownership and dependency wiring
    settings.py      # Explicit configuration
tests/               # Offline unit, integration, TLS, and Qt tests
scripts/             # Development, security, verification, and build tools
development-plans/   # Plan and execution evidence
examples/            # Synthetic sample data
```

I install the package with `uv sync` before running it. Both command entry points,
the debugger, tests, and Windows build use the same package. No application Python
scripts live at the repository root, and the repository verifier enforces that rule.
Module launchers are also available as `python -m cold_mailer` (CLI) and
`python -m cold_mailer.ui` (desktop), using the installed project environment.

## Current capabilities

I can create and reopen campaigns, import CSV/XLSX contacts with row diagnostics,
write manual drafts or generate them using an explicitly selected Gemini model,
review the exact final message, and approve each revision. Editing content or a
sender invalidates pending approvals. Accepted and uncertain messages are immutable.

Messages and campaign briefs/templates autosave in the background by default,
including incomplete drafts and recipient-specific instructions. I can turn
autosave off under Settings. The first
edit removes approval before the debounce window; every later send requires review
and approval again. Saved revisions are available from the editor. Navigation waits
for a save acknowledgment before switching recipients or campaigns, then replays
the requested navigation. Manual mode offers Save/Discard/Cancel. Save failures retain the
editor text for retry or copying.

The History tab keeps exact sender/recipient/content snapshots for every new
transport attempt, with outcome filters, background search, pagination, local-date
filters, configurable display timezone, and formula-protected UTC CSV exports.
CLI filters accept `--since` / `--until` ISO-8601 instants with explicit offsets.
Existing profiles migrate to schema v4 with a pre-upgrade
backup. Legacy sender rows require Google/Microsoft sign-in and old pending approvals
are cleared. Old attempts without snapshots remain marked unknown. The database stays
in rollback journal mode pending verification of a patched SQLite WAL runtime.

Optional additive jitter samples a value in `[0,1)` seconds after each attempt.
The next due time is saved, so restarting does not resample the interval. Real
OAuth API sending enforces at least five seconds after the previous completion, plus jitter;
longer sender intervals still apply. This pacing does not guarantee delivery or
avoid filtering. AI generation uses at most two concurrent requests; sending remains
serialized. Settings and History remain usable during provider operations.

Contact import now previews columns and sample values, saves reusable mappings,
records source/review notes, and refuses a source changed after preview. Sending
freezes the visible audience and its approved revisions; later imports or edits
cannot expand a run. **Campaign tools** provides optional timezone/weekday sending
windows, persistent request budgets, source review, revision comparison/restore,
local reply-file review, outcome reports, backup restoration, and separate workspace
opening. Sending windows hold messages for a later explicit run; they do not send
automatically. Request costs use my optional planning value and are not billing
guarantees. Local EML feedback requires review and does not connect to an inbox.

The shared GUI/CLI engine journals attempts before transmission, enforces sender
pacing and rolling daily limits, checks suppression, supports cancellation, and
recovers interrupted attempts as uncertain. A repeated run does not replay accepted
or uncertain messages. Three attempts per message are permitted; retryable messages
are eligible only after the retry delay and an explicit later run. There is no
unattended retry scheduler or background auto-send.

This is an early development build. Hosted development, security, and CodeQL
checks pass. Real-provider seed tests, signing, hosted Windows installer acceptance,
clean-machine upgrades, remaining schema/fault acceptance, and production acceptance
remain open. Credentials are owner-confirmed revoked/rotated and reachable Git
history has been sanitized. The [remediation record](development-plans/security-remediation-01.md)
tracks verification and the remaining GitHub cache/support follow-up.
The owner has submitted the GitHub Support ticket. My
[first live-testing record](development-plans/live-testing-01.md) documents the initial
HTTP 503/504 failures. [Live Testing 02](development-plans/live-testing-02.md) confirms
four successful `models/gemini-3.1-flash-lite` requests, including desktop editing,
autosave, candidate rejection, and restart checks. That is the tested recommendation
for the current project's screenshot limits. Bulk AI quota governance, real personal-account
OAuth consent, and mailbox seed verification remain open; no live email was sent.

## Development setup

I use Windows x64 with Python **3.14.7** and **uv 0.12.9**. The runtime and development
dependencies are declared in `pyproject.toml` and resolved in `uv.lock`; I retired
the old hand-maintained `requirements.txt`.

```powershell
uv --cache-dir .uv-cache sync --locked --all-groups
uv --cache-dir .uv-cache run --locked cold-mailer-desktop
```

The desktop opens without credentials or network access. It uses a per-user
`ColdMailer` application-data profile, not the repository's old `config.db`.
For a separate profile:

```powershell
uv --cache-dir .uv-cache run --locked cold-mailer-desktop --data-dir C:\Temp\ColdMailer-Demo
```

For a completely synthetic rehearsal with fake AI/SMTP and no credentials:

```powershell
uv --cache-dir .uv-cache run --locked cold-mailer-desktop --demo
```

Demo uses a temporary profile, disables live access, and deletes its synthetic data
when closed. Simulated acceptance is clearly labelled and transmits no email.

## Desktop workflow

I can choose **System**, **Light**, **Dark**, or **Contrast** from the header's **Theme** selector
or **Settings > Appearance**. Changes apply immediately and persist in the current
profile. System follows the operating system's appearance. Theme changes preserve
unsaved drafts and never enable network access.

Settings also contains smooth-scrolling and reduced-motion toggles. Mouse wheels
use a short eased animation; native pixel-based touchpad events retain their normal
behavior. **Commands** or **Ctrl+K** opens blueprint, saved-filter, variable-picker,
checklist, history, and diagnostic actions. **Ctrl+S** saves, **Ctrl+F** finds
recipients, and **F1** shows keyboard help. Editor previews show approximate narrow
and wide plain-text wrapping with deterministic quality hints. **New candidate**
generates for only the selected recipient and preserves the current draft until
I explicitly accept the candidate.

Settings offers encrypted backups with an authenticated, versioned AES-GCM format.
I keep the passphrase separately: it cannot be recovered. OS-stored passwords and
API keys are excluded from both plaintext and encrypted database backups. Support
bundles show the exact allowlisted local diagnostics before saving, exclude paths,
messages, contacts and credentials, and are never uploaded automatically.

```powershell
uv --cache-dir .uv-cache run --locked cold-mailer doctor
uv --cache-dir .uv-cache run --locked cold-mailer history --outcome accepted
uv --cache-dir .uv-cache run --locked cold-mailer history --query example.com --export C:\Temp\mail-history.csv
uv --cache-dir .uv-cache run --locked cold-mailer backup C:\Temp\campaigns.cmbak --encrypted
uv --cache-dir .uv-cache run --locked cold-mailer restore C:\Temp\campaigns.cmbak C:\Temp\RestoredProfile\campaigns.sqlite3 --encrypted
```

Exports and backups contain private mail data. Export/restore destinations must be
new files; restored pending work is held uncertain and cannot replay automatically.
The [Windows packaging guide](packaging/windows/README.md) covers the EXE installer,
unsigned MSIX preview, CI inputs, checksums, and remaining signing/install gates.

The campaign workspace uses resizable recipient/editor panels. Smaller windows
scroll instead of shrinking fields or hiding button text. **Brief and activity**
opens the AI brief, message template, and activity log; the log also opens when an
operation starts. Sender accounts and Settings use separate, scrollable cards.

1. Configure the publisher's [OAuth registrations](development-plans/personal-account-setup.md),
   enable **Live access**, then choose **Sign in with Google** or **Sign in with Microsoft**
   under **Sender accounts**. The system browser handles account selection and sending
   consent. Only personal Gmail/Microsoft accounts are supported. Reusable tokens go
   to the OS credential store; the sender identity is read-only. There is no mailbox
   password/app-password, arbitrary SMTP host, or company-account connection flow.
2. In **Campaigns**, create a campaign and import CSV/XLSX contacts. The
   [example CSV](examples/contacts.example.csv) contains synthetic data and reserved
   example addresses; it is not a live recipient list. Legacy `.xls` is unsupported.
   Review the header mapping and sample rows, optionally save the mapping, and
   record source notes before accepting. Choose one sender or explicitly rotate
   new contacts across all sender accounts.
   The sender assignment is stored before review; rotation respects each account's
   pacing and daily limits rather than bypassing them.
3. Open **Brief and activity**, enter the brief/template, and save the campaign. In **Settings**,
   configure an explicit Gemini model and save its API key to OS storage.
4. Enable **Live access** only when requesting real provider calls. **Generate
   drafts** generates subject/body and renders the wrapper before review. It does
   not overwrite existing edits or approve content. Manual drafting works offline.
5. Select a message, edit the subject and final body, **Save draft**, then select
   it again and **Approve revision**. Unsaved edits cannot be approved.
6. **Dry run** reports local message-state counts without provider calls. It does not
   prove credentials, deliverability, or future quota availability. The send path
   rechecks approvals, suppression, attempt budgets, and pacing.
7. **Send approved** requires live access and a visible confirmation.
   The frozen audience contains the currently visible recipients. Optional sending
   windows, quotas, approval, and suppression are rechecked at each claim.
   **Stop operation** requests cooperative stop; in-flight I/O has a 30-second
   timeout. The UI remains available for stop/close while worker operations finish.
8. Inspect message states after the operation. Provider acceptance is not confirmed
   delivery. An uncertain result requires checking provider evidence and explicitly
   reconciling accepted versus not sent; it is never automatically retried.

Settings also supports suppression, bounded SPF/DMARC presence diagnostics, and
database backups. DNS presence is not a validity or deliverability guarantee.
Detailed UI operation logs are bounded and session-only; attempt outcomes persist.

In **Campaign tools**, **Review a local reply file** accepts a bounded `.eml` file.
I review the content and choose reply, opt-out, or note. Linking a reply/opt-out
requires the recipient From and original Message-ID references; it does not prove
authorship. An explicitly recorded opt-out suppresses pending mail to that address.
**Restore a backup** requires a new empty workspace and holds restored pending
work. Opening that workspace starts a separate instance without copying credentials.

## Command line

```powershell
uv --cache-dir .uv-cache run --locked cold-mailer --help
uv --cache-dir .uv-cache run --locked cold-mailer --data-dir C:\Temp\ColdMailer-Demo diagnostics
uv --cache-dir .uv-cache run --locked cold-mailer --data-dir C:\Temp\ColdMailer-Demo create "Example campaign"
```

The CLI exposes `campaigns`, `senders`, `connect-account`, `disconnect-account`, `import`, `messages`, `edit`,
`approve`, `dry-run`, `generate`, `run`, `reconcile`, `suppress`, `backup`, and
`restore`. Use each subcommand's `--help` for arguments. Account connection opens
the system browser and accepts `google` or `microsoft`. Network operations require the global `--live` option before
the subcommand; default operation is offline.

Exit codes currently implemented: `0` success, `1` file/storage failure, `2`
validation/configuration error, `3` definitive or retryable send/generation failures,
`5` uncertain transmission, and `130` Ctrl+C. There is no CLI background stop command
yet. A dry run is a local inspection, not authorization to send.

I read a root `.env` only with an explicit `--development` option. The canonical
development variables are `GOOGLE_GENAI_API_KEY` and `GENAI_MODEL`; `API_KEY` is a
development-only legacy alias. No model is selected or changed silently. GUI and
CLI also share the saved model preference and the OS-stored API key.

To load the ignored root `.env` for desktop development:

```powershell
uv --cache-dir .uv-cache run --locked cold-mailer-desktop --development
```

Live access still requires explicitly enabling it in the desktop. Provider failures
now include safe HTTP status hints in the operation log without exposing raw
provider responses or automatically retrying requests.

## Backups and legacy files

The root `.env`, contact CSV, old `config.db`, and `secret.key` remain local and
ignored. The replacement application does not open or migrate them automatically.
Password-based sender creation and legacy credential import have been retired.
Existing campaign/history data remains readable; legacy passwords cannot authorize
the production send path. Connect a supported personal account explicitly before sending.
The owner confirms historical credentials have been revoked or rotated; they must
not be reused for live tests.

Backups exclude passwords. `restore SOURCE DESTINATION` creates a new SQLite file;
it never overwrites an existing profile. Restored pending messages are held as
uncertain because a backup may predate later sends. Reconcile those outcomes and
re-enter credentials as needed before resuming in the restored profile.

## Verification

```powershell
.\scripts\verify.ps1 -Mode Fast
uv --cache-dir .uv-cache run --locked python scripts/install_tools.py
.\scripts\verify.ps1 -Mode Full
.\scripts\verify.ps1 -Mode Security
```

Fast runs lint, formatting, types, repository/document checks, and unit tests.
Full also runs the complete offline suite and enforces 90% overall coverage and
95% for the critical engine/storage/transport/domain modules. Tests isolate data
and credentials. The TLS fixture opens only a loopback SMTP server; ordinary tests
deny sockets. No normal verifier sends real email or calls Gemini.

The installer downloads pinned, SHA-256-verified Gitleaks/actionlint binaries into
ignored `reports/tools`. Security additionally audits the locked dependencies,
runs Bandit, and scans reachable Git history. Fresh remote and reconciled local
history scans report zero findings after remediation, without scanner allowlists.
Hosted development, security, and CodeQL checks pass for the rewritten application
checkpoint. GitHub secret scanning and push protection are also enabled.

I can regenerate synthetic light/dark previews of every page without opening a
live profile or contacting providers:

```powershell
uv --cache-dir .uv-cache run --locked python scripts/preview_ui.py --width 1000 --height 650
```

Snapshots and size/scale results are written to ignored `reports/ui-preview/`.

To install the local commit hooks after setting up the project and scanners:

```powershell
uv --cache-dir .uv-cache run --locked pre-commit install
```

## Build status

```powershell
uv --cache-dir .uv-cache build
uv --cache-dir .uv-cache run --locked python scripts/check_artifacts.py
```

The wheel includes only the `cold_mailer` package from `src/`; source archives exclude credentials,
databases, local reports, and caches. Windows directory builds use the pinned
PyInstaller dependency. Unsigned development artifacts are not production releases;
signing, installed-app acceptance, upgrade/rollback, licensing review, and hosted
artifact verification remain gates in the plan.

Build an unsigned directory preview with `scripts/build_desktop.ps1`. The executable
is `dist/desktop/ColdMailer/ColdMailer.exe`; keep its `_internal` folder beside it.
`dist/desktop/development-manifest.json` records source hashes and clearly marks
the uncommitted/unsigned state. A hidden native Windows startup check can use
`--smoke-test --data-dir SOME-ISOLATED-PROFILE`; this never enables providers.
