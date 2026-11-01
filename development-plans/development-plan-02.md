# Development Plan 02: Durable Email History and Responsive Desktop Workflows

Date: 2026-10-19 (Asia/Karachi).

Scope override dated 2026-10-20: [Plan 03](development-plan-03.md) replaces the
generic SMTP/company-account requirements below with explicit personal Google
Gmail or Microsoft Outlook OAuth sign-in. Earlier app-password, SMTP-host, legacy
credential-import, and organizational-account tasks are historical and no longer
define supported production sending. Other unfinished Plan 02 obligations remain.

Status: active implementation. The owner authorized autonomous implementation of
this plan and the additional feature backlog on 2026-10-19. Requirements remain
open for additions. [Execution 03](execution-03.md) records current implementation,
verification, remaining local work, and owner-dependent release gates;
[Execution 02](execution-02.md) retains the preceding baseline. Unchecked tasks below remain
open unless that execution record explicitly establishes their acceptance.
No commit, push, or history rewrite is authorized in this implementation phase.

Subsequent owner instructions authorized development commits/pushes and then
historical-secret remediation. The current scope, verified isolated rewrite,
credential-rotation confirmation, approved eight-branch publication and local cleanup,
and remaining GitHub cache/support follow-up
are tracked in [Historical Secret Remediation 01](security-remediation-01.md).
The older phase restrictions above describe the implementation baseline.

The owner subsequently authorized bounded live AI testing. The
[Live Testing 01 record](live-testing-01.md) records successful model metadata
checks and failed generation attempts, including the explicitly approved stable
model trial. [Live Testing 02](live-testing-02.md) subsequently confirms four working
Gemini 3.1 Flash-Lite requests and the bounded source desktop journey. Bulk model-aware
RPM/TPM/daily quota admission, broader semantic evaluation, SMTP seed verification,
and packaged live acceptance remain open; request-count budgets alone do not close
the provider quota requirement.

Plan 01 is complete as a closed foundation phase. Its unfinished obligations are
transferred here without being marked implemented. See the
[closed Plan 01](development-plan-01.md), the historical
[execution evidence](execution-01.md), and the separate
[feature proposals](features-and-improvements.md).

## Navigation

- [Scope and baseline](#scope-and-baseline)
- [Requirements and acceptance](#requirements-and-acceptance)
- [Smooth scrolling](#smooth-scrolling)
- [SQLite history and schema evolution](#sqlite-history-and-schema-evolution)
- [Individual messages and editing](#individual-messages-and-editing)
- [Autosave and recovery](#autosave-and-recovery)
- [Pacing jitter and scheduling](#pacing-jitter-and-scheduling)
- [Concurrency and resource ownership](#concurrency-and-resource-ownership)
- [Safety across the application](#safety-across-the-application)
- [EXE and MSIX delivery](#exe-and-msix-delivery)
- [Verification and performance](#verification-and-performance)
- [Ordered execution](#ordered-execution)
- [Carryover and decisions](#carryover-and-decisions)
- [Inherited Plan 01 specification](#inherited-plan-01-specification)

## Scope and baseline

The application remains a local Windows desktop product using Python, uv,
PySide6, SQLite, OS credential storage, explicit AI model selection, and SMTP.
Keep application code in `src/cold_mailer/`; tests, tooling, documentation, and
packaging remain outside the installed application's business modules.

Interpret "multi-support" as concurrent, bounded background work and responsive
UI operation, with account-aware coordination. Multi-account configuration already
exists. This does not introduce multiple users, a web backend, or uncontrolled
multiple processes writing to the same profile. Retain one application owner per
profile; allow independent operations within that owner through explicit coordination.

### What already exists

| Area | Current implementation | Plan 02 increment |
| --- | --- | --- |
| SQLite | Per-user `campaigns.sqlite3`, schema version 1; campaigns, messages, attempts, sender configuration, suppression, preferences. | Versioned migrations, richer durable history, immutable content snapshots, and History UI. Extend this database rather than creating a disconnected sent-mail database. |
| Individual content | Every message row has its own recipient, subject, body, revision, approval, and sender-email approval snapshot. Generation iterates per recipient. | Explicit per-recipient instructions, selective regeneration, safer editor navigation, richer revision history, and autosave. Preserve the existing behavior. |
| Attempt timing | Attempt start/finish epoch timestamps and classified outcomes are persisted. | Explicit submission/acceptance metadata, local-time presentation, policy snapshots, sampled gaps, due times, and provenance for incomplete old records. |
| Sending safeguards | Approval fingerprint, short SQLite transactions, rolling daily budget, fixed sender interval, suppression, bounded attempts, uncertain-outcome holds, cooperative stop. | Durable jitter, shared quotas across jobs, account health holds, feedback handling, and cross-operation safeguards. |
| Background work | A Qt worker handles one foreground operation; the whole tab set is disabled while it runs. Thread cleanup is joined without blocking. | Bounded concurrent jobs, selective editing locks, fair queues, a database writer, per-job cancellation, and a responsive UI. |
| Appearance | Saved light/dark/system themes, consistent controls, scrollable cards, resizable editor panels. | Smooth wheel behavior, native touchpad handling, reduced-motion preference, and measured scrolling responsiveness. |
| Distribution | Locally verified unsigned PyInstaller directory preview and wheel. | Actual EXE installer, MSIX package, GitHub build workflows, install/upgrade/uninstall verification, signing, and hosted evidence. |
| Quality | Last recorded run: 99 offline tests and 94.26% combined coverage; local static/workflow/source checks pass. | Maintain these gates and add meaningful feature/fault/installer tests. These baseline numbers are historical evidence, not a new test run for this plan. |

The owner can add requirements before execution. Give every addition a stable
identifier, rationale, affected modules, data migration impact, safety impact,
acceptance evidence, dependency, and execution step. A proposal in the separate
feature file does not automatically become a release commitment.

### Precedence over the inherited specification

The explicit Plan 02 contracts below supersede conflicting older assumptions:
independent jobs may overlap within one profile owner; autosave is configurable;
timing supports additive jitter; installer delivery must cover both EXE and MSIX.
Older references to a single foreground worker or the first release's narrower
scope are baseline context, not instructions to undo these new requirements.
Existing approval, suppression, uncertainty, credential, and preservation rules
remain mandatory. Retain inherited F01-F13, N01-N05, and E00-E23 identifiers.

## Requirements and acceptance

All entries below are pending implementation or extension, even where a partial
foundation exists. Record actual source changes, tests, and artifact evidence
when closing a requirement; documentation alone cannot close an implementation gate.

| ID | Requirement | Required evidence | Execution step |
| --- | --- | --- | --- |
| R02-01 | Smooth, predictable scrolling throughout the desktop with optional animation and reduced motion. | Wheel/touchpad/nested-view tests and measured native captures at 100%/200% scaling. | P02-03 |
| R02-02 | SQLite retains drafts and the exact subject, body, sender, recipient, outcome, and date/time for each send attempt. | Schema/migration tests, immutable history tests, history UI/CLI parity, and restart verification. | P02-01, P02-04 |
| R02-03 | Every recipient owns independently editable generated content and preferences. | Two-recipient isolation, selective regeneration, stale-result, revision, and approval tests. | P02-05 |
| R02-04 | Toggleable autosave preserves edits with clear saving/error state. | Restart, toggle, navigation, conflict, close, full-disk, and concurrent-send tests. | P02-06 |
| R02-05 | Toggleable additive pacing jitter supports `5 + U[0,1)` seconds without overriding stronger limits. | Injected clock/randomness tests, persisted due-time recovery, cancellation, and cross-job quota tests. | P02-07 |
| R02-06 | Bounded concurrent work preserves UI responsiveness, database ownership, fairness, and correct outcomes. | Stress, queue saturation, deadlock/starvation probes, selective locking, and orderly shutdown. | P02-02, P02-08 |
| R02-07 | Safety rules apply consistently to import, generation, editing, persistence, transmission, recovery, and release. | Failure matrix and cross-feature invariant tests; no blind replay or secret leakage. | Every step |
| R02-08 | GitHub Actions builds a real Windows EXE installer around the frozen application. | Workflow validation, downloaded installer/checksums, isolated install/launch/upgrade/uninstall evidence. | P02-09 |
| R02-09 | GitHub Actions builds a valid MSIX with a verified identity, version, payload, and signing/test policy. | Manifest validation, appropriate install tests, state/credential behavior, and artifact provenance. | P02-10 |
| R02-10 | Existing security, production, verification, and release obligations survive Plan 01 closure. | Reconciled carryover register, credential/history remediation, hosted runs, and final acceptance evidence. | P02-00, P02-11, P02-12 |

## Smooth scrolling

### Interaction contract

- [ ] Audit all campaign, sender, settings, history, table, popup, and editor scroll
  surfaces. Use a reusable presentation component rather than separate ad hoc handlers.
- [ ] Preserve high-resolution `pixelDelta()` input when available. Animate coarse
  `angleDelta()` wheel input with short easing, accumulate sub-notch deltas, and
  coalesce repeated wheel events into a current target instead of queuing animations.
- [ ] Respect natural-scroll direction, horizontal input, gesture phases, keyboard
  scrolling, scrollbar dragging, text selection, and caret visibility. Do not apply
  synthetic inertia twice to a precision touchpad gesture.
- [ ] At an inner view's boundary, allow sensible scroll chaining to its parent;
  do not trap wheel input in a short editor or move both parent and child for one event.
- [ ] Start with a measured 120-180 ms coarse-wheel transition; clamp targets to
  current bounds and cancel/rebase on resize, model reset, page change, or close.
  These are proposed tuning values, not measured performance claims.
- [ ] Add profile settings `ui.smooth_scroll.enabled` (proposed default on) and
  `ui.reduced_motion` (`system`, `on`, `off`). Explicit reduced motion wins; keep
  immediate, usable scrolling when animations are disabled or system detection
  is unavailable. Document the platform detection fallback.
- [ ] Never use `sleep()` in a wheel handler. Do not modify spin boxes or combo
  values merely because the pointer passes over them while the page is scrolling;
  require deliberate focus/interaction.

Proposed implementation: `ui/scrolling.py`, using event-loop-owned animations for
coarse wheel deltas. Evaluate QScroller for touch/flick surfaces separately; do
not steal left-button text selection or assume it fixes mouse wheels by itself.
Use Qt's [wheel-event contract](https://doc.qt.io/qt-6/qwheelevent.html) and
[QScroller documentation](https://doc.qt.io/qt-6/qscroller.html) during implementation.

### Acceptance

- [ ] Rapid wheel reversal changes direction promptly without a long animation tail.
- [ ] No overscroll, stale timer access, field collapse, accidental value changes,
  duplicate movement, or lost keyboard navigation on every relevant page.
- [ ] Verify mouse wheel, precision touchpad, nested text/table views, and reduced
  motion on native Windows. Headless tests alone cannot certify input feel.

## SQLite history and schema evolution

### Record model

Use the existing profile database as the authoritative ledger. SQLite itself is
not a new dependency or separate server. Keep passwords/API keys out of it.

| Record | Required fields and rules |
| --- | --- |
| `messages` | Stable message/campaign/contact/sender IDs, current recipient address, current editable subject/body, state, revision, created/updated UTC timestamps, current instruction reference, and approval metadata. |
| `message_revisions` | Append-only saved subject/body and recipient/sender snapshots, version, origin (`manual`, `generated`, `autosave`, `restored`), generation reference, saved timestamp, and content hash. Coalesce keystrokes before creating revisions; retention is explicit. |
| `send_attempts` or extended `attempts` | Attempt/run/message/revision IDs, exact sender and recipient envelope addresses, subject/body snapshots, MIME Message-ID, content hash, start/submission/finish/acceptance timestamps as available, outcome, sanitized code, and uncertainty/reconciliation metadata. Capture before network use. |
| `campaign_runs` | Immutable run settings, selected IDs/revisions, pacing/limit policy version, queue state, start/end, cancellation reason, counters derived from attempts, and resumability state. |
| `schedule_state` | Sender/account quota ownership, sampled jitter, effective delay, next-eligible UTC time, attempt/run reference, retry/cooldown source, and version/lease metadata. |
| `recipient_instructions` | Contact/message scope, user-supplied facts/preferences, instruction version, generation scope, and update time. Never overwrite another recipient's instructions. |
| `preferences` | Versioned non-secret appearance, scrolling, autosave, editor, and default pacing settings. Scope and fallback precedence are documented. |
| `history_events` | Bounded, versioned lifecycle events with stable IDs, state transition, timestamp, and safe reason; no raw provider exception dumps or credentials. |
| Existing sender/suppression records | Retain referential integrity and historical identity even when an account is renamed, disabled, or its current email changes. |

The names are a proposed schema contract. Choose additive migration-friendly
details during P02-01; do not recreate/drop the database or silently duplicate it.

### Timestamp and outcome semantics

- [ ] Choose one canonical UTC representation for new records: proposed integer
  Unix microseconds with `_at_us` column suffixes. Convert through timezone-aware
  UTC datetimes; display local time plus offset and permit UTC display/export.
- [ ] In the History UI, "Sent" means SMTP submission accepted by the server, not
  confirmed recipient delivery, reading, or inbox placement. Prefer an explicit
  "Accepted by SMTP" state with client-observed acceptance time.
- [ ] Keep separate creation, update, attempt-start, transmission, acceptance,
  failure, and reconciliation timestamps. Unknown timestamps stay null; an
  uncertain transmission must not receive an invented successful-send date.
- [ ] Reconciliation records evidence/source and reconciliation time. A provider
  timestamp may be entered separately with provenance; do not present the time
  of manual confirmation as the original transmission time.
- [ ] Sender/recipient/subject/body snapshots survive later account/contact edits.
  Retrying creates a new attempt; history is not overwritten by the newest result.

### Migration and durability gates

- [ ] Implement sequential migrations from v1, a schema-version registry, an
  integrity-checked backup, transactional changes, version compatibility checks,
  and rollback/recovery instructions before enabling the new schema in production.
- [ ] Preserve legacy REAL timestamps and source provenance when deriving new UTC
  fields. Mark inferred precision appropriately. Do not claim that the current
  body is the exact content of every old failed/retried attempt; unavailable old
  snapshots must display "Not captured in this application version."
- [ ] Verify the bundled SQLite library, including the frozen executable's copy,
  before enabling WAL. The current inspected Python reports SQLite **3.50.4**.
  SQLite documents a WAL-reset race fixed in **3.51.3+**, with backports including
  **3.50.7** and **3.44.6**. Require an appropriately patched runtime and review
  current advisories; a Python package audit alone does not validate this native
  library. The existing application does not explicitly enable WAL.
- [ ] Only then evaluate WAL on local disk with one writer, short readers,
  foreign keys on every connection, bounded busy handling, and measured checkpoints.
  WAL does not create parallel writers or make network-share profiles safe.
  Reference: [SQLite WAL and WAL-reset advisory](https://sqlite.org/wal.html).
- [ ] Keep outcome journaling durable; start with `synchronous=FULL` for the
  safety ledger and measure the cost. Never weaken accepted/uncertain persistence
  just to improve a benchmark. Treat write failure after transmission as a hold
  requiring recovery, not permission to resend.
- [ ] Use SQLite backup APIs for consistent backups. Include uncheckpointed WAL
  data through the API; do not copy only a live main database file.
- [ ] Test interrupted migration, full disk, read-only paths, corrupt state,
  retained old backups, missing credentials, and restore after later real sends.
  Restored pending messages stay held until reconciled against newer evidence.

### History user experience

- [ ] Add a History view with Drafts, Pending, Accepted, Failed, and Uncertain
  filters; search by sender/recipient/subject, campaign, outcome, and time range.
- [ ] Use pagination/keyset queries and indexes rather than loading every body
  into the Qt model. Open the selected immutable revision/attempt in a read-only
  detail pane with a clear timeline and exact addresses/text.
- [ ] Show queued/unsaved edits separately from durable drafts. Display date/time
  timezone explicitly, and distinguish an unknown legacy date from an empty draft.
- [ ] Offer bounded, user-requested CSV/JSON export with formula-safe CSV handling,
  field selection, and no credentials. Preserve audit/suppression information
  required for replay prevention when applying retention or deletion policies.
- [ ] Keep equivalent CLI history/detail/export commands backed by the same services.

## Individual messages and editing

- [ ] Preserve the existing one-message-per-recipient subject/body model. Shared
  campaign briefs and wrappers are defaults, not one shared final email blob.
- [ ] Add per-recipient facts/preferences and explicit precedence: global defaults,
  campaign instructions, then recipient-specific instructions. Provider input
  includes only allowed fields and user-authorized facts.
- [ ] Support generating/regenerating the selected recipient, subject only, body
  only, or an explicitly selected batch. Keep manual text until the user accepts
  a replacement; show a diff or alternate candidate before destructive replacement.
- [ ] A generation result carries message ID, source revision, instruction version,
  campaign/run ID, and cancellation token. A stale result cannot overwrite newer
  edits or another row after sorting, filtering, or changing selection.
- [ ] Store model/prompt-template version and generation provenance without API
  keys or unnecessary private contact fields. Preserve explicit model selection.
- [ ] Validation rejects unresolved placeholders, empty required text, unsafe
  headers, and invalid addresses. Manual edits receive the same validation.
- [ ] Any content, recipient, or sender change invalidates the exact approval.
  Autosave and generation never approve. Accepted/uncertain snapshots remain
  immutable; "reuse as draft" creates a new unsent message/revision.
- [ ] Selection changes cannot lose a dirty edit or save text under a new row ID.
  Keep current subject/body/editor status visible throughout background operations.

Acceptance: generate distinct synthetic messages for two recipients, customize
one, regenerate only the other, sort/filter/reselect, restart, and verify exact
independence and approval hashes through both GUI and CLI.

## Autosave and recovery

### User contract

- [ ] Add a visible, profile-persisted Autosave on/off setting, proposed default
  on for drafts, with clear Saving, Saved at time, Unsaved, and Save failed states.
  Manual Save remains available in both modes.
- [ ] Proposed debounce: 800 ms after an edit, maximum five seconds of continuous
  unsaved typing before scheduling a save. Coalesce pending saves for the same
  message; do not create a new database revision for each keystroke.
- [ ] Include subject, body, per-recipient instructions, and explicit campaign
  brief/template changes in a documented autosave scope. Password/API-key fields
  always require explicit secure-store actions and never enter autosave payloads.
- [ ] A save is "Saved" only after the database commit acknowledgment matches
  the captured message ID, revision, and edit generation. A UI timer firing or a
  queued write is not persistence.
- [ ] When off, retain explicit Save/Discard/Cancel navigation and close prompts.
  Turning off does not erase existing drafts or undo an in-flight transaction;
  turning on offers/schedules the current dirty draft safely.
- [ ] On page/recipient/profile changes and close, flush through the coordinator
  or offer Save/Discard/Cancel. A failed save keeps the text recoverable and
  dirty. Do not close while a user-requested final save is unresolved.

### Concurrency rules

- [ ] Capture immutable save payloads on the GUI thread and commit off it. Never
  read a QTextDocument or widget from a background thread.
- [ ] Use compare-and-swap revisions. Reject/resolve conflicts rather than
  last-writer-wins overwrite. Return results only to the matching editor context.
- [ ] The first edit must block eligibility for sending immediately, before the
  debounce expires. Serialize dirty-edit registration, approval invalidation,
  claims, and snapshot creation through one application coordinator/writer.
- [ ] If an attempt claim wins first, its immutable snapshot is locked; later
  editing must be refused or fork a new unsent draft. If editing wins first, that
  message cannot be claimed until its saved revision is explicitly reapproved.
  Do not rely solely on a disabled GUI button for this invariant.
- [ ] Generation, autosave, history viewing, suppression, and sending share stable
  IDs and version checks. Shutdown stops new work, resolves pending saves, joins
  workers nonblockingly, and closes database connections on their owner threads.

Tests must cover typing during generation, row switches during a pending save,
autosave toggling during a write, stale acknowledgments, approval/send races,
duplicate notifications, disk failure, crash recovery, and credential-field exclusion.

## Pacing jitter and scheduling

### Exact requested behavior

The user's five-second example becomes a five-second minimum waiting period
plus a sampled fraction of a second. Jitter spreads timing/load; it does not
make mail legitimate, guarantee delivery, or bypass provider restrictions.

```text
u = injected_random_fraction()                 # 0 <= u < 1
effective_base = max(requested_base, account_floor, application_floor, provider_floor)
sampled_gap = effective_base + (u * jitter_max_seconds if jitter_enabled else 0)
next_eligible = max(previous_attempt_finished + sampled_gap,
                    provider_cooldown, retry_due_time, quota_reset, allowed_send_window)
```

For an effective base of 5 seconds and maximum jitter of 1 second, the waiting
gap lies in `[5, 6)` seconds; `u = 0.37` gives 5.37 seconds. It is measured after
the preceding completed attempt, so network duration and stronger limits may
make actual start-to-start spacing longer. Never promise an exact wall-clock cadence.
If the account floor is still 30 seconds, a campaign requesting 5 uses at least
30 seconds plus its configured jitter; show this in the run preview.

- [ ] Add persisted enable/disable, base-seconds, and maximum-addition settings
  with campaign defaults and explicit per-run snapshots. Proposed maximum-addition
  default is 1 second; existing 30-second sender defaults remain until deliberately
  changed. Validate finite numbers, supported bounds, and a positive live-send
  application floor; zero-delay fake tests do not authorize zero-delay live sending.
- [ ] Make override precedence explicit in the UI/CLI. Display requested and
  enforced timing, whether jitter is active, and why a stronger cooldown applies.
- [ ] Sample once when reserving the next slot and persist both gap and due time.
  Do not reroll repeatedly while waiting, after a UI refresh, or after restart.
- [ ] Use monotonic elapsed time while running, UTC due times for restart, and
  conservative handling of sleep/resume or backward clock changes. Never send a
  catch-up burst when the machine wakes or quota windows reopen.
- [ ] Wait through interruptible events/timers, not a sleeping GUI or a busy loop.
  Cancellation stops the next attempt immediately; an in-flight SMTP operation
  keeps its bounded timeout and durable acceptance/uncertainty rules.
- [ ] Share per-account/provider quotas and reservations across all campaigns and
  jobs; rotating sender accounts must not circumvent an applicable aggregate limit.
- [ ] Keep retry backoff separate from ordinary pacing. Respect server cooldowns,
  bounded retry counts, authentication failures, suppression, and uncertain holds.
- [ ] Policy edits cannot silently accelerate a reserved slot or mutate an active
  run. Apply safer increases promptly; review decreases for a later explicit run.

Acceptance uses injected random values at 0, 0.37, and just below 1; invalid
negative/NaN/infinite settings; fake clocks; delayed transports; cancellation;
restart; concurrent jobs; quota exhaustion; and policy edits. Tests perform no
real sleeping or live sends. No statistical test should make CI flaky.

## Concurrency and resource ownership

Concurrency reduces avoidable waiting; it does not by itself prevent deadlocks,
starvation, or lag. Bound resources and verify invariants under stress.

| Owner | Proposed responsibility and initial bound |
| --- | --- |
| GUI thread | Widget/model changes and immutable request capture only; no provider calls, disk-heavy queries, or blocking joins. |
| Job coordinator | Stable job IDs, state machine, cancellation tokens, per-message edit/claim ordering, admission control, and bounded queues. |
| Database writer | One thread-owned write connection; serialize journal, edits, policy, and migration writes. Never pass a connection across threads. |
| Database readers | A small bounded reader pool; short transactions, paginated history, and read snapshots. No indefinite reader blocking checkpoints. |
| AI workers | Start with at most two concurrent requests, further limited by provider/model quotas. Expose supported limits and tune from measurements. |
| SMTP dispatch | Start with one global active send, one lane per sender, and a fair queue. Additional parallel account lanes require quota/safety evidence. |
| Import/export/diagnostics | Bounded jobs/chunks; queue work or explain capacity rather than spawning unlimited threads. |
| CPU-heavy work | Add a process pool only after profiling demonstrates need. Do not move Qt widgets or shared SQLite connections into subprocesses. |

- [ ] Define a lock order and small critical sections; never hold application
  locks or a database write transaction while waiting on network I/O, user input,
  another worker, or the GUI thread.
- [ ] Use fair round-robin/weighted admission across campaigns/accounts. Bound
  outstanding work (proposed initial queue capacity 128) and coalesce draft writes.
  Backpressure stays visible; the GUI must not block waiting for queue space.
- [ ] Give journal reservations/outcomes priority without indefinitely starving
  autosave, cancellation, or interactive reads. Reserve capacity for safety writes;
  stop dispatch if durable recording cannot be guaranteed.
- [ ] Protect suppression, quotas, and message claims transactionally. One sender
  cannot have overlapping reservations even if two campaigns request work together.
- [ ] Keep unrelated pages usable. Lock only the entity/operation being mutated;
  do not disable the entire application for a long import, generation, or send.
- [ ] Coalesce progress updates and bound logs; a worker flood must not monopolize
  the event queue. Use stable IDs and operation generations for every callback.
- [ ] Make cancellation idempotent and expose queued/running/waiting/cancelled/
  completed/failed states. Apply deadlines and permit safe recovery from stuck jobs.
- [ ] Retain Qt worker/thread references until a zero-timeout join confirms native
  cleanup; use owned timers and QObject slots. Do not force-terminate a worker or
  close its connection from another thread.
- [ ] Instrument queue depth, admission wait, DB busy retries, transaction time,
  UI event latency, worker count, and completion rates without exposing message text.

## Safety across the application

| Boundary | Required controls and failure behavior |
| --- | --- |
| Import | File/expanded size and row limits, header mapping/validation, duplicates, encoding diagnostics, no formula execution, suppression checks, cancellable chunks. |
| AI generation | Explicit model/key, minimal contact fields, request budget and timeout, bounded retries, structure validation, stale-result rejection, no fabricated unsupported claims or automatic approval. |
| Editing/autosave | Stable-ID payloads, immediate approval invalidation, revision conflicts, visible commit status, no autosaved credentials, no replacement of immutable sent content. |
| Database | Patched native runtime gate, migrations/backup, foreign keys, short transactions, bounded contention, immutable attempt snapshots, clear full-disk/read-only handling. |
| Sending | Exact current approval, secure TLS, credential redaction, per-account/provider limits, durable claim before network, jitter/backoff floors, suppression and account health checks. |
| Uncertainty/restart | Never replay accepted/uncertain mail automatically. Persist holds and reconcile evidence explicitly; write failures after transmission stop the affected dispatch lane. |
| Feedback | Auth/quota errors pause the relevant lane; add reviewed bounce/complaint/unsubscribe ingestion and durable suppression without assuming SMTP acceptance is delivery. |
| UI/jobs | Bounded queues, explicit live mode and confirmation, per-job stop, no auto-send at startup, safe reduced-motion behavior, no silent loss of dirty drafts. |
| Backup/export | Consistent snapshots, redaction, explicit destinations, recipient privacy, formula-safe CSV, restore holds, and verifiable recovery. |
| Packaging/CI | No real data or secrets, scoped assets, verified tool downloads, read-only default permissions, signing isolation, artifact hashes/provenance, install/uninstall data preservation. |

Add circuit-breaker thresholds and cooldown ownership for repeated auth, quota,
transport, and storage failures. Thresholds must be configurable within safe
bounds, tested, and visible; "Safety" is not a claim that an account cannot be blocked.

## EXE and MSIX delivery

These are implementation deliverables for Plan 02; workflow YAML is not added by
this planning-only change. Keep the existing checks and directory-preview builder.
New workflows must generate downloadable artifacts without publishing automatically.

### Shared build and version contract

- [ ] Add `.github/workflows/build-windows-exe.yml` and
  `.github/workflows/build-windows-msix.yml`, using shared checked-in packaging
  helpers under `scripts/` and manifests/installer definitions under `packaging/`.
- [ ] Start with Windows x64. Resolve Python/uv/tool/native-SDK versions explicitly,
  sync from the lockfile, run required checks, freeze the same application payload,
  and verify SVGs, Qt image plugins, credentials backend, and patched SQLite runtime.
- [ ] Take the application version from package metadata. Use one tested mapping
  to Windows/MSIX four-part versions and enforce platform field limits. Keep Store
  identity/version rules as an explicit channel decision, not an assumed capability.
- [ ] Support manual branch previews with a blank optional `release_tag`. An
  explicit tag must exist and match the package version; a plain version string
  must not be passed blindly as a checkout ref. Resolve and record the exact SHA.
- [ ] Treat workflow inputs as data with allowlisted modes and structured process
  arguments. Do not interpolate arbitrary tags, paths, or publisher text into shells.
- [ ] Produce artifacts named with version, architecture, source SHA, and mode;
  include SHA-256 checksums, build manifest, tool/lock hashes, dependency/license
  inventory, and a statement of signing status. Record dirty local previews honestly.

### EXE installer

- [ ] Keep PyInstaller's directory payload separate from the installer. An EXE
  application file alone is not an installer. Proposed wrapper: pinned, verified
  Inno Setup with a per-user installation under LocalAppData and no routine admin
  requirement; confirm channel/branding before implementation.
- [ ] Define a stable installer AppId, installation directory, Start menu shortcut,
  optional desktop shortcut, version metadata, uninstall entry, icon, and running-app
  handling. Use official [Inno Setup privilege settings](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm).
- [ ] Test clean install, path with spaces/non-ASCII, launch without Python/uv,
  repair/reinstall, upgrade, blocked downgrade, and uninstall. Preserve user profiles
  by default; any optional data removal needs a clear, separate operator choice.
- [ ] Validate signatures in signed mode, timestamping, exact installed file hashes,
  and a synthetic first-launch/history/autosave workflow after installation.

### MSIX package

- [ ] Use a checked-in AppxManifest template and SDK MakeAppx helper with stable
  Name, Publisher, application ID, x64 architecture, supported Windows baseline,
  required desktop capabilities, visual assets, and executable entry point.
  Validate using Microsoft's [MakeAppx guidance](https://learn.microsoft.com/en-us/windows/msix/package/create-app-package-with-makeappx-tool).
- [ ] Keep install files immutable. Verify actual packaged LocalAppData/profile
  paths, OS keyring service identity, first launch, and EXE-to-MSIX transition
  behavior. Do not silently move/delete an existing profile or its credential refs.
- [ ] Separate unsigned build/manifest checks, disposable test-signed installation,
  and real signed distribution. A normal distributed installer needs the selected
  trusted signing/channel policy; publisher and certificate identity must match.
- [ ] Windows 11 has a special unsigned test-install route using a distinct
  publisher OID and `Add-AppxPackage -AllowUnsigned`, normally elevated for executable
  packages. It is a separate debug identity, not the ordinary release install or
  upgrade path. Keep that optional mode isolated from customer packages, following
  Microsoft's [unsigned test-package guidance](https://learn.microsoft.com/en-us/windows/msix/package/unsigned-package)
  and [signing overview](https://learn.microsoft.com/en-us/windows/msix/package/signing-package-overview).
- [ ] Disposable CI test signing may use a generated test certificate trusted only
  inside that runner. Never upload private keys/PFX/passwords or modify a user's
  certificate trust store as a build side effect. Real signing requires the owner's
  chosen identity/channel and protected credential setup.
- [ ] Test package validation, first install, launch with no development environment,
  settings/history persistence, version upgrade, identity mismatch, unsupported
  schema/downgrade refusal, uninstall/reinstall retention policy, and clean removal.

### Workflow security and actual acceptance

- [ ] Use read-only permissions by default, bounded timeouts, cache/artifact scope,
  full verified action SHAs, and audited external tools. Evaluate GitHub's workflow
  dependency lockfiles where supported; otherwise retain full SHA pinning. Follow
  [GitHub's secure-use reference](https://docs.github.com/en/actions/reference/security/secure-use).
- [ ] Fork/PR builds get no signing secrets. Keep signing and publication on trusted
  refs/protected environments. Do not combine untrusted checkout with privileged
  `pull_request_target`/`workflow_run` artifact handling.
- [ ] Define stable aggregate check names and failure propagation; skipped/cancelled
  jobs cannot masquerade as passed required build/install checks. Retain useful
  sanitized logs without uploading databases, signing keys, or real messages.
- [ ] Local actionlint/PowerShell/manifest/helper tests are required. Hosted workflow
  success additionally needs fresh run URLs for the current workflow commit,
  downloaded artifacts, matching manifests/checksums, and install results.
- [ ] A workflow edit requires a new run. Rerunning an older run retains its old
  source/inputs. A dispatch or successful checkout is not evidence of a working
  installer. Verify both EXE and MSIX independently on a clean Windows machine.
- [ ] The no-commit instruction remains in force for this planning pass. Subsequent
  pushes, dispatches, signing setup, and publication are distinct execution actions;
  none is claimed to have occurred here.

## Verification and performance

### Deterministic tests

| Area | Required cases |
| --- | --- |
| Scrolling | Coarse/pixel deltas, reversal, horizontal scroll, nested edges, resize, reduced motion, popup/input controls, selection/caret preservation, shutdown. |
| History | Sender/contact edits after send, repeated attempts, exact immutable content, null legacy fields, UTC/local/DST presentation, large paginated searches and bounded exports. |
| Migrations | v1 fixtures, interrupted steps, incompatible/future versions, integrity failure, full/read-only disk, patched native SQLite detection, WAL backup/restore and checkpoint behavior. |
| Recipient content | Distinct subjects/bodies, only-one-recipient edits, selected regeneration, stale generation/save callbacks, sorting/filter changes, manual-only use, approval invalidation. |
| Autosave | Debounce/coalescing, toggles, max unsaved duration, navigation/close, conflicts, failed writes, restart, credential exclusion, simultaneous claim/edit ordering. |
| Timing | Exact bounds with injected RNG, floors/override precedence, no reroll, cancellation, resume/clock shifts, quota sharing, auth/uncertain holds, no catch-up bursts. |
| Concurrency | Saturated queues, fair admissions, reader/writer contention, bounded workers, progress floods, cancellation deadlines, rapid repeated jobs, nonblocking cleanup, no leaked threads. |
| Installers | Branch/tag/version validation, malformed inputs, unsigned/test/real signing separation, wrong publisher, absent resources/runtime, install/upgrade/downgrade/uninstall with preserved state. |
| Security | Current source/history/native dependency scans, redacted errors, no real data/credentials in tests or artifacts, and negative gates that fail on known synthetic defects. |

Keep ordinary tests offline with synthetic profiles. Use fake clocks/RNG/waits;
allow loopback only for explicit local transport fixtures. Authorized provider
seed tests remain a separate, bounded gate with named accounts/recipients/model.
Maintain lint, formatting, types, strict warnings, at least 90% combined coverage,
and at least 95% in critical domain/engine/storage/transport modules. New scheduling,
editing, migration, and coordinator safety logic needs similarly meaningful coverage.
Do not add empty tests or tests that only repeat implementation constants.

### Proposed measured budgets

Measure on a documented Windows reference machine and in installed builds; tune
after an initial baseline instead of claiming hardware-independent guarantees.

| Operation | Initial target and measurement |
| --- | --- |
| Typing, stop feedback, and common UI actions | p95 event response under 100 ms; no synchronous provider/disk waits on GUI. |
| Scrolling | Aim for a 60 Hz presentation budget (about 16.7 ms/frame); record p95 stalls and behavior under simultaneous background work. |
| Autosave | Submit after the configured debounce; target a normal local commit acknowledgment within one second after submission, with bounded backlog and visible failure. |
| History search | Target first page under 300 ms on a synthetic 100,000-message ledger using indexes; avoid reading all bodies. |
| Cancellation | Stop new dispatch immediately; an in-flight operation obeys its timeout. Display the reason if waiting on a provider. |
| Resource bounds | Demonstrate configured worker/queue caps, stable memory during repeated import/generate/scroll/save cycles, and fair queue wait rather than unlimited growth. |

Accessibility includes keyboard reachability, status text that does not rely on
color, screen-reader review, zoom/DPI, reduced motion, focus visibility, and clear
save/conflict/error messages. Run a prolonged mixed-workload soak and failure
injection before declaring the new coordination reliable.

## Ordered execution

Each step ends with a concrete reviewable result. Record outcomes in a future
`execution-02.md`; do not overwrite the historical Plan 01 execution evidence.

| Step | Work sequence and output | Exit gate |
| --- | --- | --- |
| P02-00 | Reconcile inherited obligations and verified foundation; record selected scope and outstanding security actions. Preserve private files and uncommitted work. | Every carryover has an owner/status/evidence or remains explicitly open; no undocumented deletion or history rewrite. |
| P02-01 | Validate/update the bundled SQLite runtime; design revision/attempt/history schema; add sequential v1 migration, backups, indexes, fixtures, and recovery. | Lossless known data, honest unknown legacy fields, migration/fault tests, patched-runtime gate before WAL. |
| P02-02 | Introduce job coordinator, bounded queues, writer/read ownership, cancellation/context IDs, lock order, and observability. | Simultaneous synthetic jobs remain bounded; no duplicate claims, stale UI writes, starvation, or unsafe shutdown. |
| P02-03 | Build reusable smooth scrolling, reduced-motion preferences, nested input behavior, and native visual/performance checks. | All surfaces and input devices behave predictably at compact/large sizes and 100%/200% scaling. |
| P02-04 | Add History Qt model, filters, read-only immutable detail/timeline, pagination, timezone display, and shared CLI queries/export. | Exact archived content/identities/times survive edits/restarts; legacy unknowns remain explicit. |
| P02-05 | Add recipient instructions, candidate regeneration/diff, stable-ID editing contexts, and immediate approval invalidation. | Two-recipient independence and stale-result/claim/edit race contracts pass. |
| P02-06 | Add profile autosave toggle, debounce/coalescing, writer acknowledgments, failure state, and navigation/close recovery. | No silent lost edits, wrong-row writes, auto-approval, or credential persistence. |
| P02-07 | Add pacing policy snapshots, injectable additive jitter, due-time persistence, shared quotas, interruptible waits, and retry/cooldown integration. | Five-second example has the documented bounds; stronger floors and uncertainty/suppression always win. |
| P02-08 | Integrate the complete mixed workflow and selective UI locks; tune fairness, progress coalescing, scrolling, and history queries under load. | Stress/soak/fault and accessibility/performance evidence meet agreed budgets; deadlocks are detected/recovered, not assumed impossible. |
| P02-09 | Implement EXE installer scripts/definition/workflow, version/ref resolver, artifacts, checksums, and isolated install tests. | Fresh hosted build/install evidence matches source SHA and preserves synthetic user state across upgrade/uninstall policy. |
| P02-10 | Implement MSIX manifest/assets/helper/workflow, channel/signing modes, identity/version rules, and isolated install tests. | Fresh hosted MSIX evidence verifies the intended identity, payload, profile/keyring behavior, and signed/test policy. |
| P02-11 | Finish inherited credential rotation/history cleanup, current/native security reviews, required hosted checks, dependency/license inventory, and authorized live seed tests. | No hidden scanner suppression; published remediation and tested artifacts have evidence. External owner actions are explicit. |
| P02-12 | Clean-machine install/upgrade/rollback/recovery, operator docs, incident drills, maintenance ownership, release checklist, and explicit release decision. | All committed requirements have verified evidence; deferred proposals are listed separately. No automatic release declaration or publication. |

P02-03 can proceed alongside storage design. P02-04 depends on P02-01; P02-05/06/07
depend on coordination and persistence contracts. Installer scaffolding can begin
earlier, but final artifacts must use the integrated, verified payload. Security
containment can proceed independently and remains a release blocker throughout.
Do not hold all useful offline development hostage to external signing/rotation,
and do not hide those external gates when describing completion.

### Planned module ownership

| Location | Responsibility |
| --- | --- |
| `domain/` | Immutable revisions, timing policies, lifecycle/outcome contracts, validation, and typed ports. |
| `application/` | Editing/history use cases, scheduling/admission coordination, autosave save requests, cancellation, and cross-interface policy. |
| `infrastructure/` | SQLite migrations/queries, thread-owned storage adapters, provider/DNS/credential adapters, and backup/export implementation. |
| `ui/` | Smooth scrolling, editor/save-state presentation, History models/views, settings, and GUI-owned animations/timers. |
| `scripts/` | Repeatable quality/security/package checks, ref/version resolution, native runtime verification, and build/install orchestration. |
| `packaging/` | Installer definitions, AppxManifest templates, original visual assets, and channel identity templates without private signing material. |
| `tests/` | Focused domain/integration/Qt/packaged tests and synthetic migration/stress fixtures. |

## Carryover and decisions

### Transfer rules

Plan 01 closes administratively as the delivered foundation phase. Unfinished
implementation/verification is not rewritten as success. The inherited specification
below preserves every original unchecked obligation and its surrounding acceptance,
commands, tables, security procedure, and E00-E23 runbook. Some broad checkboxes
describe capabilities already implemented locally but missing complete acceptance;
reconcile those against `execution-01.md` instead of blindly implementing them again.

### Lossless transfer inventory

The source Plan 01 contained **199 unchecked checklist items**, plus requirements
and acceptance procedures in tables/prose. All 199 are retained, with their complete
surrounding specification, in the inherited section at the end of this document.
The source document had 11 checked foundation items; those are historical evidence,
not 11 newly completed Plan 02 tasks. Ordered carryover IDs below refer to the
unchecked items in document order; retain them when reconciling status.

Original Plan 01 SHA-256 before closure:
`45f4d4c9b66f5e7ca6802eb8f9690b767ee9d1aa155468ebd9fca354598514de`.

| Original section | Unchecked items transferred | Carryover IDs |
| --- | --- | --- |
| Section 05: Reproducible Foundation with uv | 1 | C01-001 through C01-001 |
| Section 06: Credentials and Git History Remediation | 5 | C01-002 through C01-006 |
| Section 07: Backend Correctness and Recovery | 27 | C01-007 through C01-033 |
| Section 08: PySide6 UI Redesign | 7 | C01-034 through C01-040 |
| Section 09: GitHub Actions CI and Security Validation | 8 | C01-041 through C01-048 |
| Section 11: Required Regression Scenarios and Completion Evidence | 12 | C01-049 through C01-060 |
| Section 13: Product Contract and Requirements Traceability | 3 | C01-061 through C01-063 |
| Section 14: Developer Bootstrap and Daily Workflow | 6 | C01-064 through C01-069 |
| Section 15: Linting, Typing, and Documentation Standards | 6 | C01-070 through C01-075 |
| Section 16: Deterministic Testing and Verification Strategy | 15 | C01-076 through C01-090 |
| Section 17: Data Schema, Migration, Backup, and Retention | 10 | C01-091 through C01-100 |
| Section 18: Execution State, Network, and Content Contracts | 6 | C01-101 through C01-106 |
| Section 19: Production Runtime and Environment Separation | 9 | C01-107 through C01-115 |
| Section 20: Usability, Accessibility, and Performance Budgets | 7 | C01-116 through C01-122 |
| Section 21: CI Workflow Design and Failure Validation | 6 | C01-123 through C01-128 |
| Section 22: Windows Packaging, Signing, and Release Verification | 4 | C01-129 through C01-132 |
| Section 23: Step-by-Step Execution Runbook | 55 | C01-133 through C01-187 |
| Section 24: Operations, Incident Response, and Final Readiness | 12 | C01-188 through C01-199 |

New R02/P02 identifiers complement these carryovers. A broad carryover can close
only after all its acceptance evidence is satisfied or an explicit scope decision
is recorded. A locally implemented part can be linked to its existing test instead
of rewritten. Inherited prose requirements remain binding even when they have no
checkbox; retaining the complete specification prevents losing those obligations.

### Decisions to settle before affected implementation

| Decision | Proposed starting point | Gate/owner |
| --- | --- | --- |
| Final feature scope | This plan's explicit requirements; separate proposals need promotion and acceptance. | Owner before release scope freeze. |
| SQLite runtime | Patched runtime verified in source and frozen package; select an upgrade path after wheel/packager compatibility checks. | P02-01 maintainer. |
| Autosave | On by default, 800 ms debounce, five-second maximum pending typing interval; profile toggle. | Owner review before P02-06. |
| Pacing | Existing account floor retained, configurable additive maximum default 1 second, explicit toggle; no bypass of stronger policies. | P02-07 policy review. |
| Initial concurrency | Two AI requests, one global SMTP lane initially, one writer, bounded readers/jobs. | P02-02 measurements and provider quotas. |
| History retention | User-visible policy; preserve minimum replay/suppression evidence and unknown legacy provenance. | P02-01/P02-04 data policy. |
| EXE wrapper | Per-user Inno Setup around the frozen payload, subject to tool/license verification. | P02-09 owner/maintainer. |
| MSIX channel/identity | Choose sideload, Store, or both; obtain real publisher/application identity and signing setup. | Owner before release signing/publication. |
| Profile continuity | Explicit EXE/MSIX migration and credential re-entry if namespace/path changes; no silent shared writable profile. | P02-10 installed testing. |
| External verification | Real credential rotation, remote history coordination, hosted workflow permissions, clean machine, and bounded live recipients. | Owner actions plus maintainer evidence. |

Until these decisions are finalized, keep candidate additions separate and leave
affected acceptance gates open. This plan can grow without changing the closed
status or historical evidence of Plan 01.

## Transferred execution gates

The following open execution gates are transferred from the historical execution
record. They remain required even when the new feature work proceeds in parallel.
The last local record reports six historical secret findings; rotation, coordinated
history remediation, native/runtime security review, hosted acceptance, and release
certification are not closed by completing Plan 01's foundation phase.

- E01: provider credential rotation, isolated history-filter rehearsal, remote
  rewrite coordination/publication, and fresh-clone verification.
- E04/E20: hosted workflow runs, fork/permission/negative-check demonstrations,
  required branch rules, and repository feature availability. No push was performed.
- Full schema evolution beyond the initial version, corrupt/full-disk migration
  rehearsals, stale-backup ledger reconciliation with external evidence, and portable
  credential recovery. The restore implementation holds pending messages uncertain.
- Automatic scheduling, full campaign-run event retention, recipient feedback
  ingestion, account pause/circuit-breaker controls, and comprehensive retry policy.
- AI semantic evaluation and live seed verification with an explicitly authorized
  account/model/recipient list. None was run against real credentials.
- WCAG-style/manual assistive-technology review, measured performance budgets,
  multi-monitor/high-DPI coverage, extended fault/soak and fresh-machine certification.
- Signing, installer/distribution channel, supported-version upgrades/rollback,
  bundled native dependency/license inventory, final artifact provenance, publication,
  and incident/maintenance-owner signoff. The first release is not declared ready.

## Inherited Plan 01 specification

This is the complete original Section 01-24 specification, retained as a lossless
transfer of unfinished obligations and their context. The opening contracts in
Plan 02 take precedence where they explicitly change scope. Historical statements
about earlier cleanup, filenames, development-only status, and completed work are
context, not new actions or new verification claims. The 199 unchecked items below
remain assigned to Plan 02 until reconciled. No unfinished work remains assigned
to the closed Plan 01 document.

## Section 01: Objective and Scope

Build a dependable Python desktop application with a shared campaign engine, a
PySide6 interface, persistent recovery, safe credential handling, reproducible
dependencies managed by `uv`, and enforced GitHub Actions checks.

This document replaces the earlier improvement response and supersedes archived
development documents. Keep future plans in this directory with sequential names
such as `development-plans-02.md`; update this plan when architecture changes.

The current change expands documentation. Preserve the relocated v4 source as the
migration baseline and preserve the existing local contact file, environment
settings, database, encryption key, and editor configuration. Cleanup evidence
below describes earlier work; it does not authorize deleting runtime data during
implementation. Develop and test replacements against synthetic data first.

History rewriting, remote force pushes, provider credential rotation, repository
settings changes, and production email tests are separate execution steps. This
plan does not claim they have happened.

## Section 02: Audit Findings and Evidence

The preceding audit parsed 29 Python files without syntax errors, reviewed v4's
generation and sending workflows, compared earlier versions, and exercised
isolated methods with fake AI, SMTP, and UI collaborators. No live email was sent.
The full GUI, clean dependency installation, and provider integrations were not
validated. Do not confuse mocked reproductions with end-to-end verification.

| Priority | Finding | Evidence and required improvement |
| --- | --- | --- |
| Critical | Credential material is committed | `.env`, populated v3/v4 databases, their matching Fernet keys, and hardcoded API-key strings in v3 and a root helper were tracked. Token authentication confirmed the keys match the password tokens without revealing passwords. Rotate credentials, remove current tracking, then remediate history. Credential validity was not tested. |
| High | Model configuration is evaluated too early | In v4 `ai_generator.py:40`, the default is calculated during import, before `app_ui.py:48` loads dotenv. The reproduced default is the string `None`, including after a later environment update. Resolve configuration at construction time. |
| High | AI configuration differs between entry points | GUI paths use `API_KEY`, while the AI wrapper and CLI also expect `GOOGLE_GENAI_API_KEY`; the CLI does not load dotenv consistently. Use one validated settings contract. |
| High | Failed generation is marked complete | Failed and cancelled runs both emitted `GEN_DONE` and displayed `Generated 1/1 contacts`. Track successful, failed, and cancelled outcomes separately. |
| High | AI placeholders can be transmitted | Unavailable AI returns nonempty placeholder strings that pass the send checks. Fail closed and require valid, approved final content. |
| High | Concurrent operations corrupt state | Generation can replace an active worker handle and clear its cancellation event. Loading replacement contacts can receive the old contact's copy by index. Use stable IDs, operation IDs, immutable snapshots, and a controlled lifecycle. |
| High | Campaign recovery is absent | Drafts, approvals, logs, and send results live in memory. A repeated run processes recipients again. Persist campaign state and attempt outcomes. |
| High | SMTP transport regressed | v4 always uses STARTTLS, including on port 465; v2 supported implicit TLS. Make transport mode explicit. |
| High | Accepted mail can be reported as failed | A reproduced disconnect failure after SMTP acceptance produced a send-failure log. Persist acceptance separately from cleanup and ambiguous transmission results. |
| Medium | Contact input lacks a clear contract | v4 does not normalize headers, require an email column, deduplicate, or normalize missing values. Restore useful v2 validation and add row-level diagnostics. |
| Medium | Dependency installation is incomplete | GUI imports `dotenv`, but `python-dotenv` is undeclared; Excel reader dependencies are also undeclared. Establish supported formats and a locked dependency set. |
| Medium | AI integration uses a legacy SDK | `google-generativeai` is deprecated. Migrate to the maintained Google GenAI SDK, preserving the explicitly selected model. |
| Medium | Delivery controls and diagnostics are weak | Fixed pacing and account rotation provide no durable suppression, account health, or delivery feedback. DNS lookup failures are reported like missing records. |
| Medium | Maintenance and delivery checks are absent | Multiple version directories, tracked bytecode, no tests or workflows, and README commands referencing nonexistent package/entry-point names. Consolidate source and validate the delivered application. |

The v2/v3 sources have been removed, so their paths above are historical evidence,
not links to surviving files. The maintained application now lives under `src/cold_mailer/`; start with
[desktop window](../src/cold_mailer/ui/window.py) and [CLI](../src/cold_mailer/cli.py).

## Section 03: Immediate Cleanup and Preservation Boundaries

### Cleanup manifest

| Target | Action | Reason |
| --- | --- | --- |
| `b2b_cold_email_tool_v2/` | Remove | Superseded source, local database/configuration, and generated caches. |
| `b2b_cold_email_tool_v3/` | Remove | Superseded source, embedded credential material, database/key, and caches. |
| `!APP_VERSIONS/` | Remove | Four ZIP snapshots, superseded PDF/DOCX plans, old campaign copy, and an app-password screenshot. Requirements are carried forward here. |
| Every existing `__pycache__/` | Remove | Generated Python bytecode does not belong in source control. |
| `Google-GenerativeAI-List-Models.py` and `List_Models.py` | Remove | One-off model inspection scripts; one contains a key literal. |
| `.env`, v4 `config.db`, v4 `secret.key` | Keep local; remove tracking | Preserve current settings while excluding secrets and state from future source snapshots. |
| `Load Contacts.csv` | Keep local; remove tracking | Preserve the user's existing modification and avoid publishing real contacts. |
| Former `b2b_cold_email_tool_v4/` contents and `.vscode/` | Move application contents to root; preserve editor settings | Remove the empty version wrapper and update imports and launch instructions. |
| `examples/contacts.example.csv` | Add | Synthetic input documenting the contact format without personal data. |

Before deletion, inventory exact targets, verify they resolve inside the workspace,
reject reparse points, and record hashes of protected files. After deletion,
compare protected hashes and review the complete Git diff. Do not recursively
delete the repository root, `.git`, or a path derived from an unchecked string.

Current-tree deletion and index removal do not remove committed history. Existing
credential exposure remains an open issue until the separate security gate passes.

- [x] Remove the obsolete directories, archive folder, helpers, and caches.
- [x] Add ignore rules for credentials, databases, contacts, environments, and outputs.
- [x] Remove local secrets and contacts from Git tracking while retaining their bytes.
- [x] Verify protected-file hashes and the cleanup diff.

Cleanup verification on 2026-10-19: all 16 protected files retained their SHA-256
hashes, including the user's modified contact CSV and the active v4 implementation.
The four retained local credential/data files are ignored and removed from the Git
index. Obsolete-file deletions are recorded in the index; no commit or remote push
has been performed. History remediation and provider credential rotation remain
open. No live campaign or provider test was run during cleanup.

Root consolidation on 2026-10-19 moves the eight Python modules, requirements,
database, and key from the version wrapper to root. The two README files are
merged, local imports and launch commands are updated, and the empty wrapper is
removed. Local database/key names and ignore rules continue to apply. Historical
path names in the audit and history-removal checklist remain relevant to Git history.

Consolidation verification: 12 unchanged files passed hash comparisons after path
mapping, including the database, key, environment, contact CSV, and editor settings.
The three edited Python files contain only the required local-import changes.
All eight root modules passed syntax/import checks with third-party dependencies
stubbed; the CLI usage path also passed without sending email or opening the GUI.
These checks do not validate a full installation or provider integration.

### Behavior to preserve during migration

- Sender management, credential recovery, CSV/Excel import, personalisation,
  prompt/template editing, body/subject generation, review/edit, and campaign logs.
- Account rotation with explicit limits, cancellation, seed tests, domain
  diagnostics, and a usable headless interface.
- Restore v2's useful implicit-TLS support, missing-value handling, required email
  column checks, and separate campaign orchestration as tested contracts.
- Seed tests use the same engine and validation as campaigns, with bounded test
  recipients; they must not bypass approval or credential checks.
- Replace old claims about guaranteed warm-up periods or delivery with measured
  provider diagnostics. Automated warm-up is not an application dependency.

## Section 04: Target Architecture and Repository Structure

Organize application Python modules in the installable `src/cold_mailer/` package.
This supersedes the temporary root-module layout while keeping the obsolete
version directory removed. Group domain rules, application services, infrastructure
adapters, and Qt presentation into persistent packages. Keep domain rules independent
of Qt, SMTP, Gemini, and SQLite. The GUI and CLI call the same application services.
Scope build discovery to the application package and keep local state excluded.
Tests, development tooling, examples, documentation, and GitHub configuration have
their own top-level support directories.

```text
.
|-- src/
|   `-- cold_mailer/
|       |-- __init__.py
|       |-- __main__.py             # CLI module launcher
|       |-- bootstrap.py            # Dependency wiring and profile lifecycle
|       |-- settings.py             # Explicit validated configuration
|       |-- cli.py                  # Shared-engine CLI commands
|       |-- domain/
|       |   |-- __init__.py
|       |   |-- models.py           # Entities, validation, outcomes, approval hashes
|       |   `-- ports.py            # Provider and credential interfaces
|       |-- application/
|       |   |-- __init__.py
|       |   `-- campaigns.py        # Campaign orchestration and cancellation
|       |-- infrastructure/
|       |   |-- __init__.py
|       |   |-- storage.py          # SQLite, attempts, recovery, backup/restore
|       |   |-- credentials.py      # OS credential adapter
|       |   |-- ai.py               # Explicit-model Google GenAI adapter
|       |   |-- smtp.py             # TLS SMTP transport and MIME composition
|       |   |-- contacts.py         # Bounded CSV/XLSX import
|       |   |-- templates.py        # Restricted message rendering
|       |   |-- dns.py              # Bounded DNS diagnostics
|       |   `-- legacy.py           # Explicit read-only legacy account import
|       `-- ui/
|           |-- __init__.py
|           |-- __main__.py         # Desktop module launcher
|           |-- window.py           # Main PySide6 window and entry point
|           |-- models.py           # Qt table models
|           |-- workers.py          # Worker lifecycle and signals
|           |-- theme.py            # Shared light/dark/system palettes and controls
|           |-- components.py       # Cards, fields, icons, and scroll containers
|           `-- assets/             # Original SVG control indicators
|-- tests/                          # Offline unit/integration/Qt/TLS tests
|-- scripts/                        # Verification, scanners, and build tooling
|-- .github/                        # Workflows and dependency updates
|-- development-plans/              # Plan and execution evidence
|-- examples/                       # Synthetic contact sample
|-- pyproject.toml
|-- uv.lock
`-- README.md
```

This is the implemented application layout. The earlier version-wrapper removal
remains in effect; persistent source organization supersedes the temporary flat
layout. All application imports use the `cold_mailer` namespace. Development
scripts and tests remain outside the installed package. Runtime data remains in
per-user profiles. Future resources and migrations belong to their owning package.
Avoid adding a web server or distributed queue for this single-user desktop
scope; a persistent local engine and controlled worker are sufficient initially.

## Section 05: Reproducible Foundation with uv

- [x] Select and document a supported Python version after verifying wheels for
  PySide6, the AI SDK, Excel readers, and packaging tools on Windows. Pin it in
  `.python-version` and express the supported range in `pyproject.toml`.
- [x] Define package metadata, a build backend, and GUI/CLI entry points in
  `pyproject.toml`. Use `uv` to generate and maintain the committed `uv.lock`.
- [x] Use dependency groups for development, UI tests, and security tooling;
  install the groups needed by each CI job explicitly.
- [x] Add PySide6, the maintained Google SDK, template rendering, DNS, and credential
  storage adapters. Keep pandas only if justified by import requirements; explicitly
  support `.xlsx` with its reader and either add `.xls` support or reject it clearly.
- [x] Keep secrets out of project metadata, lockfiles, logs, caches, and build output.
- [x] Standardize one API key setting and an explicit model identifier. Provide a
  blank `.env.example`; reserve dotenv for development and prefer OS storage in
  the desktop app. Missing settings must produce actionable errors.
- [x] Resolve settings when starting a service, never in default argument expressions
  or module import side effects. Preserve the selected model during SDK migration.
- [ ] Validate clean Windows installation, package imports, console entry points,
  `uv build`, and installation of the resulting wheel in a separate environment.

The foundation commands below are implemented. The independent wheel environment
and local Windows executable have been checked; a clean-machine production install
remains a separate gate in Execution Record 01. Use a project-local cache when needed:

```powershell
uv sync --locked --all-groups
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pyrefly check
uv run --locked pytest
uv build
```

Use `--locked` in validation so stale metadata fails rather than silently changing
the dependency resolution. Use a project-local `.uv-cache` if Windows cache
permissions require it; never commit that cache. See the
[uv project guide](https://docs.astral.sh/uv/guides/projects/) and
[lock/sync semantics](https://docs.astral.sh/uv/concepts/projects/sync/).

## Section 06: Credentials and Git History Remediation

Treat the committed credential material as exposed. Rotation is required even
when later scans or history cleanup succeed. Preserve current local files until
their settings can be migrated, but do not mistake preservation for secure storage.

### Credential lifecycle

- [ ] Revoke and replace affected Google keys and SMTP/app passwords with the
  providers; record completion without recording the credential values.
- [ ] Store desktop credentials in Windows Credential Manager or user-bound
  protection, behind an interface that can support other platforms later.
- [ ] Move SQLite state to a per-user writable application-data directory.
  Keep credential references in SQLite rather than reversible passwords with
  a portable key beside the database.
- [ ] Implement an explicit, tested migration of legacy accounts and keys. Handle
  missing/wrong keys without silently generating a replacement over existing data.
- [ ] Hide secrets from dataclass representations, exception messages, prompts,
  logs, telemetry, screenshots, reports, and packaged artifacts.

### History cleanup procedure

Perform this as a dedicated operation after protecting uncommitted work.
The user's modified contact file must remain byte-for-byte intact.

1. Inventory branches, tags, renamed sensitive paths, and embedded literals.
   Preserve a restricted recovery copy outside the publishable repository.
2. Rotate credentials first and coordinate a write freeze before rewriting.
3. Rehearse in a fresh isolated clone using a current `git-filter-repo` supporting
   `--sensitive-data-removal`. Remove sensitive paths and redact literals in retained
   files using private replacement rules; never commit those rules.
4. Cover `.env`, all historical databases/keys/configs, contact lists, the password
   screenshot, helpers, and affected old version/archive paths, including renames.
5. Scan rewritten reachable history and review the rewritten application tree.
6. Review affected refs before publishing the rewrite. Preserve unrelated work;
   do not blindly mirror-push refs that should remain untouched.
7. Coordinate the remote update, then verify a fresh clone. Address remaining
   pull-request/cache references through GitHub's documented process if needed.
8. Re-clone other working copies and prevent old history from being merged back.

Do not run history rewriting in this dirty working checkout. Deleting the Git
directory and reinitializing is not a substitute for the required remediation.
Remote rewrite publication is a coordinated destructive operation to review after
the local rewrite is concrete. Forks and other clones require separate handling.
Follow [GitHub's sensitive-data removal procedure](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).

## Section 07: Backend Correctness and Recovery

### Application state and execution

- [ ] Define explicit application states: idle, importing, generating, awaiting
  review, ready, sending, stopping, completed, cancelled, and failed. Reject
  conflicting commands in services as well as disabling inappropriate UI controls.
- [ ] Use stable campaign/contact/message IDs and operation-specific cancellation.
  Never apply results by mutable list index. Reject stale operation results.
- [ ] Freeze approved sender, recipient, subject, rendered body, and content revision
  for a send. Editing source content invalidates approval; in-flight content is immutable.
- [ ] A stop request prevents the next send, while an in-progress network operation
  obeys explicit timeouts. Distinguish stopping from stopped, and report partial results.
- [ ] Make shutdown orderly: request cancellation, wait within defined bounds,
  persist outcomes, release connections, and close storage after workers finish.
- [ ] Emit typed progress and outcome events, including counts of successful,
  failed, skipped, cancelled, and uncertain messages. Avoid magic strings such as `GEN_DONE`.

### Persistent data and transactions

Use versioned SQLite migrations and repository interfaces. Start with these data
sets: sender profiles/credential references, contacts, campaigns, approved messages,
send attempts, suppression entries, and diagnostic events. Give each worker its
own connection or serialize storage through a repository owner; disabling SQLite's
thread check is not a concurrency design. Configure foreign keys, bounded busy
timeouts, transactions, and an appropriate local journaling mode.

- [ ] Enforce uniqueness for a campaign recipient/message revision and persist the
  attempt before transmission. Define safe claim/update transactions.
- [ ] Track draft, generated, approved, queued, in-flight, accepted, retryable failure,
  permanent failure, uncertain, and cancelled states with validated transitions.
- [ ] Separate SMTP acceptance from delivery, bounce, and complaint outcomes.
  Store timestamps, attempt IDs, provider response codes, and message IDs.
- [ ] Recover interrupted in-flight attempts as uncertain unless there is reliable
  evidence of their outcome. Stable Message-ID values aid reconciliation but do
  not guarantee SMTP deduplication or exactly-once delivery.
- [ ] Resume eligible work only. Never automatically replay accepted or uncertain
  attempts. Reconcile uncertain results explicitly before retrying.
- [ ] Test backup, restore, schema upgrades, account migration, and corrupt-data
  handling with synthetic databases. Keep backups outside source control.

### Contacts, templates, and AI

- [ ] Normalize headers and missing values; preserve string identifiers and leading
  zeros. Require valid recipient fields and reject header/newline injection.
- [ ] Deduplicate within imports/campaigns using a documented address policy; avoid
  blindly rewriting case-sensitive local parts. Check suppression at send time too.
- [ ] Validate file types, sizes, encoding, and row counts; show row-level rejection
  reasons. Protect CSV exports from spreadsheet-formula execution.
- [ ] Validate template syntax and required variables before generation. Retain strict
  undefined handling and restrict template capabilities to the intended trust boundary.
- [ ] Block blank/placeholder/invalid AI outputs. Treat imported text as untrusted
  prompt data and send only allowlisted personalization fields to the AI provider.
- [ ] Use a provider adapter with explicit model selection, timeouts, bounded retries,
  rate limits, and output validation. Record model/prompt revisions without secrets
  or unnecessary recipient data. Consider generating subject/body together only
  after measuring output quality and failure handling.
- [ ] Preview the exact final message and sender before approval, with an unsaved-edit
  indicator. Regeneration must not silently overwrite reviewed copy.

### Transport and delivery controls

- [ ] Support explicit STARTTLS and implicit TLS with certificate verification;
  validate configuration and guarantee cleanup after connection/authentication errors.
- [ ] Compose validated messages with explicit envelope recipients, Date, Message-ID,
  and appropriate text/HTML alternatives when supported.
- [ ] Record transmission acceptance before cleanup. A QUIT failure must not turn an
  accepted message into a retryable send failure.
- [ ] Preserve SMTP response classifications. Use bounded retry/backoff with jitter
  for eligible temporary failures and pause accounts with invalid credentials.
- [ ] Apply sender-specific pacing and limits, a single-run ownership rule, and
  failure thresholds. Sender rotation must respect provider limits.
- [ ] Persist unsubscribe, bounce, and complaint suppression, with import and feedback
  ingestion interfaces. Never describe SMTP acceptance as confirmed inbox delivery.
- [ ] Return present, missing, invalid, or unknown domain diagnostics; join split TXT
  segments correctly. Add selector-aware DKIM checks and explain SPF/DMARC limits.
  DNS lookups run away from the UI thread and have bounded timeouts.
- [ ] Offer dry-run and bounded seed-test modes through the same engine. CLI exit
  codes and result summaries must reflect partial failure or cancellation.

## Section 08: PySide6 UI Redesign

Use Qt Widgets initially, with a main window, navigation, model/view tables, clear
forms, and a campaign review flow. Keep design resources separate from business
logic and avoid recreating the current monolithic UI module.

| Area | Expected behavior |
| --- | --- |
| Overview | Campaign summaries, actionable setup errors, recovery tasks, and accurate state. |
| Sender accounts | Add/edit/test accounts, choose TLS mode, display health and limits, and mask credentials. |
| Contacts | Import diagnostics, searchable/sortable table, duplicate/suppression indicators, and row errors. |
| Campaign editor | Prompts, templates, explicit model, autosaved drafts, generation status, and validation. |
| Review | Exact rendered messages, per-message approval, bulk review tools, and visible unsaved changes. |
| Run monitor | Accurate totals, current operation, retry/uncertain outcomes, stop state, and persistent results. |
| Diagnostics/settings | Redacted export, domain checks, storage location, provider configuration, and theme. |

- [ ] Use `QAbstractTableModel` and filtering/sorting proxies rather than constructing
  one widget per contact. Keep table rows stable across updates.
- [ ] Run blocking work in worker objects managed by `QThread` or an appropriate
  pool. Use queued signals for results; only the GUI thread updates widgets.
- [ ] Retain worker/thread references through completion, disconnect stale events,
  and clean them up deterministically. Do not use forced thread termination.
- [ ] Add keyboard navigation, accessible labels, focus states, high-DPI support,
  useful empty/error/loading states, and a restrained light/dark theme.
- [ ] Define measurable targets before release: remain responsive during network
  waits and large imports, avoid per-row widgets for 10,000 synthetic contacts,
  and document startup/memory measurements on the supported Windows baseline.
- [ ] Test with `pytest-qt`, fake services, and signal assertions. Verify cancellation,
  unsaved edits, recovery views, and close-during-work behavior on Windows.
- [ ] Evaluate Qt's deployment tools and create a reproducible Windows artifact.
  Verify startup, plugins, resources, data paths, checksums, dependency licenses,
  and exclusion of credentials on a clean machine.

See [Qt's QThread guidance](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html)
and [Qt for Python deployment documentation](https://doc.qt.io/qtforpython-6/deployment/index.html).

## Section 09: GitHub Actions CI and Security Validation

Workflows are required deliverables, not completed by writing YAML alone. Add
them with the foundation so they execute against real commands and tests. A
bootstrap check may validate the retained source earlier, but must not be presented
as validation of the future PySide6 application.

| Check | Implementation and acceptance |
| --- | --- |
| Workflow validation | Run actionlint for syntax, expressions, and supported shell checks; lint YAML. Fail invalid workflow changes. |
| Reproducible setup | Pin the uv tool and Python versions; install explicitly selected groups with `uv sync --locked`. A stale lockfile fails. |
| Formatting and types | Run Ruff checks/format validation and Pyrefly against the maintained package. |
| Backend tests | Unit and integration tests with fake AI/SMTP, temporary SQLite databases, and no production secrets. |
| UI tests | Windows PySide6 lifecycle tests plus offscreen tests where appropriate; retain a real Windows packaging smoke test. |
| Secret scanning | Gitleaks on the intended source/index snapshot and full reachable Git history with redaction and full history checkout. An unresolved history finding remains a failure. |
| Dependency vulnerabilities | Audit the exact locked runtime dependency set with pip-audit; include development/build groups on a defined schedule. Scan failure is not a clean result. |
| Static security | Configure Python CodeQL where available; use a local Python security check as a baseline. Check GitHub feature availability before relying on it. |
| Supply-chain updates | Dependabot configuration for GitHub Actions and supported Python/uv updates; review changes and regenerate lockfiles. |
| Build and artifact checks | Build the package, smoke-test installation, build the Windows desktop artifact, and inspect packaged contents for state/secrets. |

- [ ] Trigger relevant checks for pull requests, default-branch pushes, manual runs,
  and scheduled security scans. Test a fork-style PR without secrets.
- [ ] Pin external actions to reviewed full commit SHAs, default to read-only token
  permissions, and grant write permissions only to jobs needing them.
- [ ] Keep untrusted PR execution separate from privileged events and production
  credentials. Add job timeouts, sensible concurrency, and deterministic fixtures.
- [ ] Do not upload raw secret findings, contact lists, local databases, or keys.
  Redact reports and limit artifact retention. Cache dependencies without local state.
- [ ] Require zero unreviewed secret findings and zero unaccepted known dependency
  vulnerabilities. Exceptions need an owner, reason, affected scope, and expiry;
  do not blanket-ignore findings or use unconditional success fallbacks.
- [ ] Exercise negative checks using safe synthetic fixtures in an isolated test
  location: malformed workflow, failing test, controlled scanner fixture, stale lock,
  and a known vulnerable dependency fixture. Never commit an actual credential.
- [ ] Run hosted workflows for the reviewed commit, inspect every required job and
  artifact, and record the run URL, commit SHA, tool versions, and results.
- [ ] Configure required branch checks and secret push protection where available.
  Verify a failing check blocks the intended merge path.

An operational full-history scanner will report the existing exposure until history
remediation is published. Do not suppress it just to make the first run green.
An ignored local `.env` is outside the publishable snapshot; full history must still
be checked. Vulnerability scans cover known advisories and do not prove the absence
of vulnerabilities.

References: [uv on GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/),
[GitHub secure workflow guidance](https://docs.github.com/en/actions/reference/security/secure-use),
[Gitleaks](https://github.com/gitleaks/gitleaks),
[pip-audit](https://github.com/pypa/pip-audit), and
[actionlint](https://github.com/rhysd/actionlint).

## Section 10: Ordered Implementation and Acceptance Gates

This is the milestone overview. Section 23 supplies the detailed execution order;
Sections 12-24 add requirements to the earlier sections, rather than replacing
their correctness and preservation obligations. A later, more specific contract
in this plan governs an implementation detail where an earlier paragraph is broad.

| Phase | Deliverables | Gate |
| --- | --- | --- |
| 00: Current cleanup | This plan, obsolete-file removal, ignore rules, synthetic sample, and preserved local state. | Protected bytes unchanged; deletion scope verified; history risk remains explicit. |
| 01: Security containment | Credential rotation, private recovery preparation, rehearsed history filtering, reviewed remote remediation, and fresh-clone scan. | Exposed credentials revoked; published refs verified; remaining cache/fork work recorded. |
| 02: uv/package foundation | Scoped source-package build configuration, configuration contract, locked dependencies, entry points, and initial executable CI checks. | Fresh Windows setup, build, imports, lint/types/tests, and workflow validation pass. |
| 03: Reliable engine | Contact/template validation, durable schema, state machine, immutable approvals, fake adapters, and recovery. | Fault tests prove no cross-contact updates, overlapping execution, or blind replay. |
| 04: Provider adapters | Maintained AI SDK, SMTP TLS modes, timeouts, response classification, suppression, and diagnostics. | Controlled integration checks pass; model selection is preserved; outcomes stay accurate. |
| 05: PySide6 interface | Reviewed layouts, tables, editor, approval, monitor, diagnostics, and safe worker lifecycle. | Full user flow passes with fake services and a bounded authorized seed test. |
| 06: Delivery hardening | Packaged Windows artifact, clean-machine smoke test, dependency/license review, documented operations, and final CI enforcement. | Hosted checks and fresh-install evidence match the reviewed commit/artifact. |

Implement overlapping foundation/security work only where it does not obscure an
unresolved gate. Preserve the relocated legacy modules until their replacement
behavior and the installed package entry points have been verified.

## Section 11: Required Regression Scenarios and Completion Evidence

- [ ] Missing configuration fails clearly; dotenv timing cannot turn the model into
  the string `None`; GUI and CLI use the same key/model configuration.
- [ ] AI initialization, timeout, quota, blocked output, or generation failure never
  makes placeholders sendable or marks failed contacts as generated successfully.
- [ ] Cancellation reports partial progress accurately and prevents the next send.
- [ ] Importing/reloading contacts or starting a conflicting operation cannot apply
  stale content, clear another operation's stop request, or orphan its worker.
- [ ] Editing or regenerating content invalidates approval; approved final rendering
  exactly matches the immutable message supplied to the transport.
- [ ] STARTTLS and implicit TLS are verified, and failed login/connect/send paths
  close resources without hiding the original result.
- [ ] Disconnect failure after acceptance leaves the attempt accepted. A crash at
  each send boundary recovers safely, especially before acceptance is recorded.
- [ ] Restart, resume, duplicate import, and repeated run do not replay accepted mail.
  Ambiguous attempts remain uncertain until reconciled.
- [ ] Missing columns, blank cells, duplicate/malformed recipients, encoding errors,
  oversized imports, malicious headers/templates, and suppressed addresses are handled.
- [ ] Database migration/backup/restore and missing credential-store/key scenarios
  fail safely without destroying existing local data.
- [ ] UI and CLI summaries match stored outcomes; logs and exported diagnostics
  contain no credentials or unnecessary contact information.
- [ ] Fresh-clone scans, failing-check demonstrations, hosted run URLs, and clean
  Windows artifact verification are recorded before release readiness is claimed.

Record evidence with the relevant implementation change: commands, commit SHA,
hosted run URLs, sanitized results, artifact hashes, and any remaining limitations.
Keep open work unchecked. A successful syntax check, local mock test, or workflow
dispatch alone is not evidence of complete application or release reliability.

For the SDK migration, consult
[Google's current library guidance](https://ai.google.dev/gemini-api/docs/libraries).
For SMTP transport semantics, consult
[Python's smtplib documentation](https://docs.python.org/3/library/smtplib.html).

## Section 12: Coverage Gap Assessment

The earlier plan identified the main functional risks but did not fully specify
how a developer would work, how checks would be enforced, or how a user would
receive and operate a validated desktop artifact. This revision fills these gaps.

| Gap or insufficient detail | Required addition | Where defined |
| --- | --- | --- |
| Tool names without checked-in configuration | Rule sets, dependency groups, commands, and consistent local/CI entry points. | Sections 14-15. |
| Testing mentioned without fixture/isolation policy | Test levels, markers, network boundaries, clocks, coverage, warnings, and flake handling. | Section 16. |
| Features without traceable acceptance | Requirement IDs mapped to behavior, tests, and implementation steps. | Section 13. |
| Recovery described without storage boundaries | Schema, transactions, migration, backup/restore, retention, and downgrade policy. | Sections 17-18. |
| Development and installed environments conflated | Profiles, configuration precedence, writable paths, and side-effect-free imports. | Section 19. |
| UI quality described without measurable checks | Keyboard/screen-reader, scaling, capacity, startup, and responsiveness targets. | Section 20. |
| CI list without enforced merge behavior | Jobs, triggers, permission boundaries, negative checks, and evidence of hosted execution. | Section 21. |
| Packaging described without delivery lifecycle | Artifact identity, clean-machine installation, signing, upgrade, rollback, and release channels. | Section 22. |
| Broad phases without an execution procedure | Ordered steps with prerequisites, outputs, verification, and stop conditions. | Section 23. |
| Release completion without operating procedures | Redacted diagnostics, incidents, maintenance, retirement, and recovery rehearsals. | Section 24. |
| Root README contains inherited assumptions | Replace old installation/packaging and guaranteed warm-up claims when the new implementation is available. | Steps E13, E21, and E22. |

Planning is complete only when each implementation step has observable acceptance.
Application development is complete only when the corresponding implementation
and evidence exist. Neither a long document nor passing mocks alone closes a gate.

## Section 13: Product Contract and Requirements Traceability

### Supported first release and explicit limits

Target a single-operator Windows desktop application with local SQLite storage,
one controlled send operation per data profile, Google-based content generation,
and authenticated SMTP delivery. Begin with Windows 11 x64 as the proposed test
baseline; verify the selected Python/Qt/packager combination before declaring OS
support. Do not imply Windows ARM, Linux, macOS, or unsupported OS coverage from
Qt's portability. Additional targets require their own build/test evidence.

Keep application Python modules inside `src/cold_mailer/`, grouped by domain,
application, infrastructure, and UI responsibilities. Keep tests, development
scripts, plans, examples, and GitHub metadata outside the installed package. Do
not restore root-level application scripts or a version wrapper; verify package
installation and both entry points outside the checkout. This is a local desktop product, not a
hosted multi-user platform: authentication roles, cloud synchronization, automatic
bulk scheduling, and a web dashboard are outside the first release.

Preserve full body/subject editing and support manual content when AI is unavailable.
Manual content must satisfy the same validation, review, and approval rules as AI
content. Choose CSV and `.xlsx` as the initial import formats; `.xls` requires a
documented reader decision and tests before it is advertised. No attachment support
or rich HTML editor is implied; plain-text sending is sufficient for the first
release. Sanitize and test any later HTML or attachment feature separately.

### Requirement-to-verification matrix

Test filenames below are deliverables to create, not claims that tests exist.

| ID | Required behavior and acceptance | Test/evidence deliverable | Execution step |
| --- | --- | --- | --- |
| F01 | First launch opens without credentials, creates only per-user state, and explains setup. | `tests/ui/test_onboarding.py`; installed first-launch record. | E05, E14, E19. |
| F02 | Add/edit/delete/test a sender; deleting a referenced sender does not corrupt old campaign history. | `tests/integration/test_sender_lifecycle.py`. | E05-E07, E11, E15. |
| F03 | Import valid rows, reject invalid rows with reasons, and report duplicates/suppression without losing accepted rows. | `tests/unit/test_contact_validation.py`; `tests/ui/test_contact_import.py`. | E08, E15. |
| F04 | Save/reopen campaign prompts, templates, drafts, and selected configuration. | `tests/integration/test_campaign_persistence.py`. | E06-E09, E15. |
| F05 | Generate valid content with the selected model; fail/cancel/quota errors remain visible and unsendable. | `tests/integration/test_ai_adapter.py`; approved evaluation record. | E10. |
| F06 | Edit, preview, and approve the exact sender/recipient/subject/body revision; edits invalidate approval. | `tests/unit/test_approval.py`; `tests/ui/test_review.py`. | E09, E15. |
| F07 | A dry run produces a plan/report with zero outbound SMTP and zero AI calls unless separately requested. | `tests/integration/test_dry_run.py`; fake-server transcript. | E12-E13. |
| F08 | Send approved eligible messages with sender limits, correct TLS, and accurate acceptance/failure classifications. | `tests/integration/test_smtp_protocol.py`; `tests/integration/test_campaign_send.py`. | E11-E12. |
| F09 | Stop prevents subsequent sends, keeps outcomes accurate, and leaves UI responsive. | `tests/integration/test_cancellation.py`; `tests/ui/test_stop.py`. | E12, E15. |
| F10 | Restart/resume never blindly replays accepted or uncertain attempts; recovery explains available actions. | `tests/integration/test_crash_recovery.py`; packaged recovery evidence. | E12, E19. |
| F11 | Suppression, bounce/complaint import, and domain diagnostics persist and distinguish unknown from missing. | `tests/integration/test_suppression.py`; `tests/unit/test_domain_health.py`. | E08, E12-E13. |
| F12 | CLI and GUI use the same services and produce consistent persisted results and exit/status summaries. | `tests/integration/test_cli_ui_parity.py`; full offline user journey. | E13-E15. |
| F13 | Backup/restore and legacy-account migration preserve data and handle missing user-bound secrets clearly. | `tests/integration/test_data_migration.py`; restore rehearsal. | E05-E06, E19. |
| N01 | Packaged source, lockfile, installed wheel, and packaged app represent the same reviewed code/configuration. | Build manifest, wheel test, packaged smoke test. | E02, E18-E21. |
| N02 | No secrets or real contacts enter source, logs, test artifacts, or distributions. | Secret/history/artifact scans and redaction tests. | E01, E03-E04, E20-E21. |
| N03 | Quality checks are deterministic, enforced, and demonstrably fail on defects. | Local verifier, hosted required checks, safe negative-check evidence. | E03-E04, E17, E20. |
| N04 | Accessibility and performance meet the proposed measured budgets. | Accessibility checklist and reproducible benchmark report. | E14, E17, E21. |
| N05 | Production failures yield safe recovery and useful redacted diagnostics. | Fault-injection suite, incident drill, support bundle review. | E17, E19, E23. |

- [ ] Assign an implementation issue or PR to every requirement and execution step.
- [ ] Record deliberate scope changes and update this matrix, tests, and user docs together.
- [ ] Keep unresolved release decisions visible with an owner and a target gate.

## Section 14: Developer Bootstrap and Daily Workflow

### Workstation and dependency ownership

- [ ] Document Windows shell requirements, Git, the pinned uv release, supported
  Python, editor setup, and any native toolchain required by the selected packager.
- [ ] Add `.editorconfig` and `.gitattributes` for UTF-8, final newlines, consistent
  indentation, and deliberate line-ending treatment, including PowerShell files.
- [ ] Add checked-in debugger configurations for the packaged GUI/CLI with synthetic
  profiles; never store secrets in editor files or auto-start live sending.
- [ ] Make `pyproject.toml` and `uv.lock` authoritative. Retire hand-maintained
  `requirements.txt` after migration, or generate it reproducibly with its purpose
  stated in the header. Do not maintain two independent dependency catalogs.
- [ ] Scope package discovery to `src/cold_mailer` in build configuration; verify
  exact wheel contents and source equality so private data and support code cannot
  enter the application wheel. Reject application Python scripts at project root.
- [ ] Keep build-system dependency versions controlled as well as runtime versions.
  Record resolved build tools; a runtime lock alone does not pin an isolated build.

| Dependency group | Contents and use |
| --- | --- |
| Runtime dependencies | PySide6, provider/SMTP support, persistence/import/template/DNS adapters used by the installed application. |
| `dev` | Ruff, Pyrefly, and pre-commit; fast authoring and review checks. |
| `test` | pytest, coverage integration, bounded-timeout/network-isolation tools, and property-based tests where valuable. |
| `ui-test` | pytest-qt and UI-only test dependencies. |
| `security` | pip-audit and the selected Python static security scanner. |
| `build` | The chosen Windows packager and its build helpers. |

Pin non-Python tools such as actionlint, Gitleaks, and Markdown/YAML/PowerShell
linters in a tool manifest or installer script, including verified download hashes.
If a Markdown tool needs Node, record a separate tooling prerequisite and pin its
version; it is not an application runtime dependency. Prefer one maintained tool
per responsibility rather than conflicting formatters/type checkers.

### Commands and a shared verification entry point

The commands in this section are target commands after E02-E04 create the required
configuration and scripts. They must not be reported as currently available.

```powershell
uv sync --locked --all-groups
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pyrefly check
uv run --locked --group test --group ui-test pytest -m "not live and not packaged"
uv build
```

The Full verifier additionally enables configured application-only coverage and
test reports, for example after the coverage include/omit rules exist:

```powershell
uv run --locked --group test --group ui-test pytest -m "not live and not packaged" --cov --cov-branch --cov-report=term-missing --cov-report=xml:reports/coverage.xml --cov-fail-under=90 --junitxml=reports/junit.xml
```

The verifier creates the ignored report directory and separately evaluates the
critical-module threshold from the coverage data. It must not obtain a passing
percentage by measuring test code or omitting difficult application modules.

Create `scripts/verify.ps1` with `-Mode Fast`, `Full`, `Security`, and `Release`.
CI and developers use the same underlying configuration and commands. The script
must check each native process exit code, stop/aggregate failures deliberately,
restore environment variables in `finally`, use explicit working directories,
and return nonzero if any required check failed. No command may hide a failure
through a pipeline, `continue-on-error`, or an unconditional success exit.

| Mode | Checks to execute |
| --- | --- |
| Fast | Lock consistency, formatting/lint, types, relevant unit tests, and changed-document/config checks. |
| Full | Fast plus complete offline unit/integration/UI suites, coverage, installed-package wheel smoke test, and source snapshot scan. |
| Security | Source/index and reachable-history secret scans, locked dependency audits, static security, and workflow checks. |
| Release | Full and Security plus clean build, artifact inspection, packaging/upgrade checks, and readiness manifest. Privileged signing/publication remain separate steps. |

Define a separate `scripts/test-live.ps1` requiring an explicit live mode, bounded
seed-recipient allowlist, and a nonproduction account. `verify.ps1` never contacts
real mail/AI providers as a side effect. Installation and advisory lookup may need
network access; distinguish those from application network access in tests.

### Repeatable change cycle

1. Read the requirement, affected states, and current failing behavior; protect any
   unrelated working changes. Create an isolated working branch when appropriate.
2. Write an acceptance example and the smallest meaningful regression test for
   correctness, recovery, or security behavior. A prose-only change needs document
   checks, not an implementation-mirroring test suite.
3. Change the owning service/adapter first, keeping GUI/CLI behavior consistent.
4. Run targeted checks while iterating, then Fast before review and Full/Security
   as required by the change scope. Do not repeatedly rerun already-passing suites
   without a new change or unresolved concern.
5. Review diffs, generated files, dependency changes, security findings, and docs.
   Run a staged-snapshot secret check before committing; local hooks are advisory
   defense, while CI is the enforcement boundary.
6. Submit a small reviewable change with requirement IDs, behavior, verification,
   and migration/rollback implications. Re-run affected checks on the final revision.
7. Merge only after required hosted checks match that revision. Record evidence and
   update checkboxes for delivered work, not merely planned or dispatched work.

See [uv dependency groups](https://docs.astral.sh/uv/concepts/projects/dependencies/)
and [Python entry-point packaging](https://packaging.python.org/en/latest/guides/creating-command-line-tools/).

## Section 15: Linting, Typing, and Documentation Standards

### Configuration deliverables

| Configuration | Required policy |
| --- | --- |
| Ruff in `pyproject.toml` | Explicit Python target and line length; begin with `E`, `F`, `I`, `UP`, `B`, and `SIM`; use the Ruff formatter. Review rule compatibility before adding others. |
| Pyrefly configuration | Include all maintained `src/cold_mailer` modules, scripts, and tests deliberately. Require typed service/port contracts and fix missing imports; document narrow provider/Qt stub limitations. |
| pytest configuration | Explicit test roots, registered markers, strict configuration/markers, bounded waits, predictable import behavior, and warnings policy. |
| Coverage configuration | Measure application modules and branches, exclude tests/generated files/build output from measured source, and report missing branches. |
| pre-commit configuration | Pinned revisions for formatting/lint, trailing whitespace, merge conflicts, config validation, and staged-secret detection; hooks do not send mail. |
| Document/config lint | Markdown structure/fences/local anchors, YAML/TOML parsing, actionlint, and PowerShell parsing plus a selected script analyzer. |
| Dependency/tool update config | Reviewed update cadence and tool pins; changing the lockfile runs relevant tests/builds. |

- [ ] Do not blanket-ignore lint/type/security categories, unresolved imports, or Qt
  worker errors. Any suppression names a rule, explains the boundary, and is local.
- [ ] Keep domain/ports typed without unconstrained `Any`; validate untyped provider
  data at adapter boundaries. A fake satisfying an interface does not validate
  the provider's real response contract.
- [ ] Avoid duplicate formatters, automatic fixes in CI, and application behavior
  hidden inside import-time configuration. CI checks changes; authors review fixes.
- [ ] Treat project-owned deprecations and unexpected warnings as failures. If Qt
  or an upstream dependency needs a filter, scope it to the precise warning and
  record why it is safe, its owner, and the condition for removal.
- [ ] Prohibit real credentials, contact data, generated production messages, and
  machine-specific paths in examples, snapshots, and documentation.
- [ ] Add a lightweight architecture check: domain/ports cannot import Qt, storage,
  or concrete provider modules. CLI and UI call services rather than each other.

### Quality gates

Use these as proposed first-release targets, to be reviewed and fixed in E03
before implementation claims support. Changes require a documented reason;
lowering a gate just to make a failing change pass is not acceptable.

| Gate | Required result |
| --- | --- |
| Formatting/lint/type/config | Zero unexplained errors across the maintained scope. |
| Offline tests | No failing, unexpected skipped, or unexpected xfailed required tests. Missing tests/zero collection fails. |
| Coverage | At least 90% combined line/branch measurement over maintained application code; separately report critical engine/storage/approval/transport coverage targeting 95%. Configure and verify the thresholds explicitly. |
| Critical failure paths | Every enumerated acceptance, cancellation, approval, crash-boundary, and suppression scenario passes regardless of aggregate coverage. |
| Secret/dependency security | No unresolved secret findings; no unaccepted known vulnerabilities. Scanner outage or unscanned dependency is visible failure/unknown, not success. |
| Docs/commands | Commands exercised on a clean supported environment; planned commands clearly labeled until implemented. |

Coverage is a diagnostic, not proof of correct delivery. Sample high-risk mutations
such as removing an approval check or changing an accepted state to retryable and
verify the tests fail; a full mutation tool is optional if its cost is justified.

References: [Ruff configuration](https://docs.astral.sh/ruff/configuration/),
[Pyrefly configuration](https://pyrefly.org/en/docs/configuration/), and
[branch coverage](https://coverage.readthedocs.io/en/latest/branch.html).

## Section 16: Deterministic Testing and Verification Strategy

### Test levels and execution boundaries

| Level | What runs | Important distinction |
| --- | --- | --- |
| Unit | Pure validation, rendering, approvals, state transitions, retry decisions, and accounting with injected dependencies. | Fast and offline; never creates the real user's state. |
| Integration | Real temporary SQLite/migrations, credential adapter contracts, MIME composition, and controlled local SMTP/TLS fixtures. | Exercise adapters/protocols rather than stubbing every layer. |
| UI | Real PySide6 widgets/models/workers with deterministic application-service fixtures. | Assert visible state and signal lifecycle; offscreen success is not full desktop certification. |
| Offline end-to-end | Import -> draft -> generation fixture -> review -> approve -> local SMTP -> persisted outcome -> restart/recovery. | Verify actual final message bytes and storage, not only button labels or mocks. |
| Live contract/seed | Explicitly selected AI and SMTP test accounts with a small recipient allowlist and budget. | Manual/protected execution only; not the default PR suite. |
| Packaged | Actual built executable installed/launched as a standard user, including restart, migration, uninstall, and recovery. | Run against the downloaded artifact, without relying on checkout/Python/uv. |

For packaged offline tests, supply synthetic profiles and protocol fixtures from
an external harness; do not bundle real/test credentials or test fixture files into
the release. Manual-content authoring can exercise the packaged send/recovery path
when provider endpoint overrides are intentionally unavailable. Generation still
requires its own verified provider/packaged contract. Test mode must not bypass
approval, envelope validation, suppression, or production TLS policy.

Register markers `unit`, `integration`, `ui`, `e2e`, `live`, `packaged`, and `slow`.
Every test declares its applicable level; a collection check enforces that policy.
Use marker exclusions for routine offline checks and select live/packaged jobs
explicitly. Do not hide unimplemented first-release behavior behind permanent skips.

### Isolation and fixtures

- [ ] Use temporary profile directories and synthetic databases, contacts, keys,
  templates, and provider responses. Patch data-path resolution before app creation.
  Test code must not load root `.env`, open root `config.db`, or access stored SMTP
  credentials. Assert those protected paths remain untouched.
- [ ] Deny external sockets in default application tests. Allow loopback only for
  explicitly scoped local fixtures. Separate package/advisory downloads from test
  execution; a fake-network test passing does not validate TLS/provider compatibility.
- [ ] Inject wall-clock time, monotonic time, random jitter, sleep/wait behavior,
  provider clients, and credential storage. Test UTC and Asia/Karachi explicitly;
  do not depend on the runner's local timezone.
- [ ] Use `qtbot` signal waits/event-loop conditions with deadlines. Do not use
  arbitrary sleeps to make thread tests appear stable. Capture unhandled Qt worker
  exceptions and fail the test.
- [ ] Provide a real local SMTP fixture for valid STARTTLS/implicit TLS, refused
  recipients, authentication errors, connection loss, and delayed responses.
  Use a dedicated test trust root; verify invalid certificate rejection without
  disabling production verification.
- [ ] Ensure SQLite tests open multiple connections where races matter. Inject
  disk-full, read-only, lock/busy, schema mismatch, and failed-commit conditions.
- [ ] Include Unicode, whitespace/BOM headers, quoted newlines, duplicate columns,
  leading zeros, empty/malformed values, unsupported extensions, oversize files,
  spreadsheet formula prefixes, and internationalized address policy fixtures.
- [ ] Use property-based tests for parsing/state invariants where useful. Store
  deterministic reproduction seeds and minimal failing examples without real data.
- [ ] Golden MIME/prompt tests normalize dates/IDs only where those fields are not
  the assertion target. Avoid brittle snapshots of random AI prose or screen pixels.
- [ ] Close event loops, threads, sockets, and connections in teardown. Assert no
  orphan worker or leaked resource survives a test.

### Failure matrix and reliability assertions

Inject failures immediately before/after each durable boundary: approval save,
queue claim, connection, authentication, recipient acceptance, DATA transmission,
server acceptance response, accepted-state commit, cleanup, and final UI event.
Terminate a subprocess to test actual restart behavior at selected boundaries;
catching an in-process exception is not equivalent to process death.

For each case assert: persisted state, allowed retry behavior, approved-message
identity, suppression decision, visible summary, and lack of unintended extra
SMTP messages. Test network loss/resume, cancelled generation, closed window,
multiple app instances, and clock changes. A service event arriving after a closed
view must not update a destroyed widget or an unrelated campaign.

### Flake and evidence policy

- [ ] Store sanitized JUnit, coverage, crash traces, and selected synthetic UI
  captures. Avoid uploading full workspaces or environment dumps.
- [ ] A first failing required run remains a failure to investigate. Automatic
  retry may gather evidence but cannot silently convert an intermittent defect to
  accepted readiness. Any quarantine has an owner, expiry, and substitute coverage.
- [ ] Run fast tests on every change, complete offline tests before merge, UI on
  supported Windows, and slow/performance/extended fault tests on schedule and release.
- [ ] Record actual pass/fail/skip/xfail counts and collection scope. A command that
  collected no tests must not be reported as passed coverage.
- [ ] For AI, evaluate a synthetic scenario set for required structure, length,
  placeholder absence, unsupported claims, and usable subject/body content. Pin
  model/prompt revisions and record rubric results; semantic review supplements
  deterministic structural assertions without requiring byte-identical prose.

References: [pytest integration practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html)
and [pytest-qt signal waits](https://pytest-qt.readthedocs.io/en/latest/signals.html).

## Section 17: Data Schema, Migration, Backup, and Retention

### Minimum persistent records

| Record | Minimum fields and constraints |
| --- | --- |
| Schema metadata | Monotonic version, migration identifier/checksum, applied UTC timestamp, supported compatibility range. |
| Sender profile | Stable ID, email/envelope identity, host/port/TLS mode, credential reference, limits, active/paused state; no plaintext credential. |
| Contact/import | Stable ID, original address, canonical comparison key, allowlisted personalisation fields, source batch, validation result, and timestamps. |
| Campaign | Stable ID, title, prompt/template revisions, selected model, operational state, creation/update timestamps, and current owner/run reference. |
| Message revision | ID, campaign/contact IDs, frozen sender/recipient/subject/rendered body, content hash, validation result, approval timestamp/revision, and Message-ID. |
| Send attempt | Unique attempt ID, message revision, run ID, state/phase, start/end UTC timestamps, response classification, uncertainty reason, retry due time/count. |
| Suppression | Address comparison key, reason/source, effective timestamp, active state, and audit information for deliberate reversal. |
| Run/events | Stable run ID, ownership/lease metadata if needed, event type and correlation IDs; minimal redacted error details. |

Define foreign keys and uniqueness explicitly. Deleting a contact/sender must not
orphan send history or silently repoint an approved revision. Archive referenced
records or preserve an appropriate historical snapshot. Large body/log retention
must be bounded separately from safety-critical attempt/suppression information.

### Storage and concurrency contract

- [ ] Keep transactions short; never hold a SQLite write transaction while waiting
  for DNS, AI, SMTP, user input, or Qt signals.
- [ ] Atomically claim eligible work with the expected prior state/version; use a
  process/profile ownership mechanism so two app instances cannot claim it twice.
- [ ] Configure foreign keys on every connection, bounded busy retries, and explicit
  transaction handling. Choose WAL for local storage only after testing checkpoint,
  backup, and shutdown behavior. Network-shared database folders are unsupported.
- [ ] Persist state changes before reporting them as durable to the UI. If an
  accepted-state commit fails, retain/report uncertainty and prevent blind replay.
- [ ] Persist UTC timestamps and render them in the selected user timezone. Use a
  monotonic clock for elapsed waits; define conservative restart behavior for
  persisted provider budgets when the system clock changes.
- [ ] Version event/state contracts so older UI events or saved records fail safely.

### Migration and recovery procedure

1. Determine the old schema and owning application version before modifying data.
2. Stop active work, obtain exclusive migration ownership, and create a consistent
   SQLite backup with its integrity result and checksum. Do not copy a live WAL
   database file alone or treat that copy as a valid backup.
3. Apply sequential migrations transactionally where possible; record the schema
   version only when the step succeeds. External credential-store changes require
   compensating recovery logic because they cannot share a SQLite transaction.
4. Verify integrity, foreign keys, row counts/invariants, and legacy credential
   references. On failure, preserve the original and offer a clear recovery path.
5. Open migrated state only with a compatible application. A newer unsupported
   schema must cause a safe refusal rather than a guessed downgrade.
6. Rehearse restore to a separate temporary profile, including missing/wrong keys,
   unavailable OS credential storage, and a different Windows user/machine.

A restored backup may predate accepted sends. Preserve any newer attempt/suppression
ledger separately, place restored campaigns on hold, and reconcile post-backup
outcomes before offering resume. If that evidence is missing, do not assume the
backup's queued messages were never sent. Test this stale-backup scenario explicitly.

Define the backup contract: configuration/history backups may omit passwords;
restoring them can require re-entering credentials. If optional encrypted exports
are offered, document protection, handling, and recovery without storing the
export password beside the file. User-bound credentials are not portable merely
because the SQLite database is portable.

### Retention and deletion

- [ ] Set documented, user-visible retention defaults for drafts, generated bodies,
  diagnostic logs, imports, and backups; record limits in configuration and tests.
- [ ] Preserve sufficient accepted/uncertain-attempt and suppression information to
  avoid accidental resend after retention cleanup. Erasing this history must explain
  the loss of deduplication guarantees and require an explicit reset action.
- [ ] Provide export/delete operations with clear scope and confirmation for data
  loss. Never delete source contact files or OS credentials as a side effect of
  closing a campaign or uninstalling without the chosen retention policy.
- [ ] Test restore and migration from every supported release schema; do not claim
  arbitrary historical migration support without a fixture and execution evidence.

## Section 18: Execution State, Network, and Content Contracts

### Service commands and typed outcomes

Commands include create/update/import campaign, generate selected drafts, save
manual content, approve a revision, plan/dry-run, start, request stop, reconcile an
uncertain attempt, resume eligible work, suppress, export, and backup/restore.
Validate arguments and state in application services, independently of the UI.
Return typed results with IDs, outcome, counts, and a redacted error code/message.

An event contains operation/run/campaign/message IDs as appropriate, a sequence
number or version for stale-result rejection, and a typed payload. Events must not
contain credentials. Coalesce high-frequency progress events to keep the Qt queue
bounded; persist important outcomes even when a view is closed.

| Transition | Guard or failure behavior |
| --- | --- |
| Draft -> generated/validated | Valid manual content or a validated provider result; a failure remains draft/failed. |
| Validated -> approved | Exact content revision and sender/recipient identity are saved and acknowledged. |
| Approved -> queued | Revision still matches, sender is available, recipient is eligible, and run limits allow it. |
| Queued -> in-flight | One owner atomically claims the immutable revision and journals an attempt before network use. |
| In-flight -> accepted | Server acceptance is known and saved; later cleanup failure does not undo acceptance. |
| In-flight -> retryable/permanent/uncertain | Protocol phase and trustworthy response determine the classification; ambiguous transmission is uncertain. |
| Retryable -> queued | Attempt/time budget remains, due time reached, and approval/suppression/account health still pass. |
| Accepted/uncertain -> automatic resend | Forbidden. Deliberate reconciliation or a separately approved new message is required. |

Represent generation status, approval status, and delivery status separately when
one enum would conflate them. A stop request is not a completed cancellation until
the worker acknowledges its state. A campaign with partial failures is not labelled
fully successful merely because iteration ended.

### CLI result and exit-code contract

Define and test these codes in the replacement CLI; the legacy script does not
currently implement this contract. Structured output also reports per-message
outcomes, so an exit code is not a substitute for the attempt ledger.

| Code | Meaning |
| --- | --- |
| `0` | Requested operation completed successfully; an intentional no-eligible-work result is explicit in its summary and sends nothing. |
| `1` | Unexpected fatal/internal failure; preserve diagnostic context and unfinished work. |
| `2` | Invalid command, input, configuration, or unmet required approval before execution. |
| `3` | Completed campaign with one or more definitive operational failures. Intentional suppressed/skipped recipients are accounted for separately. |
| `4` | Cooperative cancellation through a supported application stop mechanism. |
| `5` | One or more uncertain transmission outcomes require reconciliation. |
| `130` | User interrupt such as Ctrl+C, after bounded cooperative cleanup. |

If several outcomes apply, preserve the interruption/cancellation identity while
reporting uncertainty explicitly in structured output and storage. For a normally
completed run, uncertain outcomes take precedence over definitive partial failure.
Never make a script infer retry eligibility solely from an exit code.

### Operational limits and failure policy

- [ ] Configure connection/read/generation deadlines, overall operation deadline,
  maximum attempts, maximum backoff, retry window, sender hourly/daily budgets,
  circuit-breaker threshold, import size, and queue capacity. Document units and
  defaults in one settings schema; test boundary/zero/negative/out-of-range values.
- [ ] Initially send serially, with bounded generation concurrency if measurements
  justify it. An account rotation rule must never bypass health, quotas, or limits.
- [ ] Recheck suppression and approval immediately before claiming/transmitting.
  Explain that an already-transmitting message cannot be recalled by a late stop
  or unsubscribe; prevent all subsequent eligible sends.
- [ ] Network errors retain protocol phase and causal information. Do not collapse
  rejected recipients, failed credentials, temporary service refusal, certificate
  failure, and uncertain DATA results into the same retry action.
- [ ] Make rate-limit and quota failures visible. AI retries may incur cost: enforce
  retry/token/recipient budgets and do not silently switch model or regenerate
  approved content. Account retries must not loop forever.
- [ ] Support explicit test endpoints and test trust settings only in isolated test
  profiles. Production must not disable TLS verification through an implicit fallback.

### Content and address policy

Store original input for diagnostics only as needed; canonicalize domain names
deliberately and define internationalized/SMTPUTF8 support. Reject multiple
recipients in a single contact field and CR/LF in envelope/header inputs. Validate
the final MIME message before submission, not just the initial CSV field.

Use Jinja's strict undefined behavior with a restricted template context. Decide
and test whether imported templates are permitted; untrusted templates require a
restricted/sandboxed environment and resource limits. Imported contact values
remain data, never template source. Validate subject length/newlines, body limits,
required placeholders, Unicode handling, and unsaved edits before approval.

Keep prompts versioned and send only the personalization fields required for the
task. Test prompt-injection-like contact notes and unsupported factual claims.
AI output is editable draft content, not an authority to bypass service rules.

## Section 19: Production Runtime and Environment Separation

### Profiles and configuration precedence

Define development, automated-test, and production profiles explicitly. A test
profile uses synthetic state and denied external network; production startup must
not infer a test profile from a stray file or expose a hidden bypass for sending.
An explicit diagnostic mode may report versions/configuration presence without
revealing values or attempting network access.

For nonsecret settings, document precedence: explicit application/CLI option,
profile-specific environment where permitted, saved user settings, then validated
defaults. Credentials use a configured OS-store reference; explicit environment
fallback is development-only. Do not accept passwords as normal CLI arguments
that enter shell history/process listings. Loading `.env` is explicit development
bootstrap behavior, not an installed-app dependency or an import-time action.

- [ ] Create one immutable settings object after validation. Show missing/invalid
  fields without printing secret values. Document default values, units, valid
  ranges, sensitivity, restart requirements, and environment/CLI mappings.
- [ ] Share settings/service construction between GUI and CLI. Importing a module
  does not create a database/window, read credentials, start threads, or contact a provider.
- [ ] Add a per-profile identifier and a safe test path override controlled by the
  bootstrap. Tests assert they cannot escape their temporary data directory.
- [ ] Preserve provider/model choice when migrating user settings; unsupported or
  retired configurations require a visible decision, not silent substitution.

### Installed application lifecycle

1. Resolve application identity, version, supported platform, and writable user
   data/log/cache paths. Use Qt standard-path APIs or one consistent path adapter.
2. Acquire a profile ownership lock. A second instance either activates the first
   UI or opens only an explicitly supported non-sending view. A crashed owner must
   not permanently lock the profile or permit simultaneous active send owners.
3. Validate settings, inspect schema compatibility, and perform any required safe
   migration/backup before enabling write/send operations.
4. Recover unfinished work conservatively and show a summary of accepted,
   retryable, cancelled, and uncertain messages before offering resume.
5. Open the UI even when credentials/network are unavailable, with draft/edit and
   diagnostics available. Never resume sending merely because the app launched.
6. On exit, reject new operations, request stop, finish/persist bounded cleanup,
   disconnect workers, close repositories, and release ownership in order.

Use per-user writable storage rather than the install directory or current working
directory. Test launching from a shortcut, a different folder, paths with spaces
and Unicode, and a read-only installation folder as a standard user. No normal
operation should require administrator rights. Cache cleanup must not delete
databases, suppression, credential references, or user-authored drafts.

### Errors, logs, and diagnostics

- [ ] Define stable error codes and user actions for configuration, authentication,
  network/TLS, rate limit, provider rejection, template, storage, and recovery errors.
- [ ] Log structured UTC events with version/run/campaign/attempt IDs and redacted
  outcomes. Do not log message bodies or recipient lists by default. Rotate logs
  by size/time and enforce retention; retry loops cannot grow logs without bound.
- [ ] Capture unhandled main/worker exceptions, persist a minimal crash marker,
  and offer a useful recovery message. Diagnostic export previews included files
  and removes credentials, bodies, contact details, local usernames, and unnecessary paths.
- [ ] Set explicit offline/proxy behavior. Use normal platform trust settings and
  fail visibly for TLS/certificate issues; do not implement insecure fallbacks.
- [ ] Record application/provider protocol versions to help diagnose compatibility
  regressions without environment dumps. Network status alone cannot prove a
  particular SMTP or AI endpoint is available.

See [Qt standard application paths](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QStandardPaths.html).

## Section 20: Usability, Accessibility, and Performance Budgets

### UI interaction specification

Document wireframes and state tables before implementing the replacement views.
Every screen specifies loading, empty, ready, validation-error, offline, partial
failure, stopping, and recovery states where applicable. Keep provider/backend
implementation details out of ordinary product flows unless they help an operator
choose a meaningful action.

- [ ] Onboarding explains sender/model setup and test mode without requiring a
  first real campaign. Credential edits are masked and never echoed to logs.
- [ ] Imports show total/accepted/rejected/duplicate/suppressed counts, reasons,
  and a preview before committing the batch. Sorting/filtering must not change IDs.
- [ ] Drafts autosave with visible saved/error state; navigation/close preserves
  edits or clearly asks about unsaved work. UI validation does not replace service guards.
- [ ] Review shows exact subject/body, sender, recipient, revision, and approval
  state. Bulk approval makes its scope/count visible and preserves per-message identity.
- [ ] The run screen displays eligible/attempted/accepted/failed/skipped/uncertain
  counts whose definitions are consistent with persisted outcomes. Stop displays
  stopping until acknowledged. Retry actions show their eligible scope.
- [ ] Recovery actions explain accepted versus uncertain outcomes in ordinary
  language. Reopening a view does not start or repeat provider work.
- [ ] Test right-click menus, selection, copy/export, focus restoration, resizing,
  confirmation dialogs, and interrupted navigation. Destructive choices identify
  exactly what data is affected and preserve a recovery path where possible.

### Accessibility acceptance

Verify all primary flows using only a keyboard, including table navigation and
dialog dismissal. Test meaningful accessible names and label associations, logical
tab order, visible focus, non-color-only status, readable contrast, text scaling,
high-DPI icons, and screen-reader announcements for errors/progress. Exercise
Windows Narrator on the packaged app. Offscreen UI tests do not substitute for
assistive-technology testing.

Test at 100%, 150%, and 200% display scale, a small usable window, and multi-monitor
movement. Long names, long errors, Unicode/emoji, and long translated-looking
labels must not hide primary actions. The first release may use English only;
keep strings centralized for later translation without claiming localization.

### Proposed engineering budgets

Fix baseline hardware, OS, dataset, power mode, build type, and measurement method
in E03/E14. These are proposed targets to validate, not current performance claims.

| Measurement | Proposed first-release acceptance |
| --- | --- |
| Warm local startup | Usable main window within 3 seconds on the documented baseline. |
| Packaged cold startup | Within 5 seconds, or revise the target with measurements before selecting a one-file bundle. |
| UI responsiveness | Ordinary UI actions respond within 100 ms at the 95th percentile; no blocking network/storage loop on the GUI thread. |
| Cancellation feedback | Visible acknowledgement within 250 ms; preventing the next send does not wait for a full throttle interval. In-flight I/O still obeys its deadline. |
| Working set | Target idle process tree at or below 250 MiB and a 10,000-contact workflow at or below 500 MiB; record actual peak and startup cost. |
| Import and list capacity | 10,000 synthetic contacts import within 5 seconds on the baseline without losing input responsiveness. Larger/oversized inputs are explicitly bounded or rejected. |
| Sustained operation | Complete a two-hour fake-provider soak with bounded queue/log growth, no orphan workers, no duplicate accepted sends, and no unexplained sustained memory growth after settling. |
| Test feedback | Fast verifier targets under 2 minutes and complete offline CI under 10 minutes; security/download/build steps are timed separately. |

Measure rather than promise these limits on all machines. If packaging/toolchain
choices exceed a budget, document the tradeoff and revise it before acceptance.
Use deterministic fake providers for load so performance tests incur no email/AI
charges. Test both steady state and error storms; bound queued progress updates.

### Complete acceptance walkthrough

Run this first against source UI/CLI, then against the actual desktop candidate
where supported. Use a fresh temporary profile, local protocol fixtures, and only
synthetic contacts. Reset between fault scenarios rather than combining unrelated
state assumptions into one brittle test.

1. Launch without credentials or network. Verify onboarding and diagnostics are
   usable, no campaign starts automatically, and only the test profile is written.
2. Configure a synthetic sender and fixture AI model; test missing fields, bad TLS
   settings, failed credentials, edit, delete, and re-entry without logging secrets.
3. Import a five-row fixture: two eligible rows, one malformed row, one duplicate,
   and one suppressed row. Verify the five-row accounting and two accepted contacts.
4. Create a named campaign, prompt/template, and drafts; close/reopen it and confirm
   persistence. Invalid templates fail before provider work.
5. Generate fixture content, simulate one failure, retry only that generation,
   and verify successful drafts and error status are not confused.
6. Edit both subjects/bodies and inspect final wrappers. Approve one revision;
   confirm the unapproved revision cannot be transmitted.
7. Change approved content or sender; verify approval is invalidated. Reapprove the
   final intended revisions and save their hashes and message identities.
8. Run a dry run. Compare planned eligibility/sender/limits with stored approvals;
   assert zero SMTP submissions and zero implicit AI calls.
9. Start the local-fixture campaign. At a controlled barrier after the first
   acceptance, stop before the next claim and verify the remaining revision is not sent.
10. Restart. Confirm the first acceptance remains recorded and no automatic resume
    occurs. Deliberately resume only eligible remaining work.
11. Independently inject a temporary rejection, permanent refusal, lost acceptance
    response, and QUIT failure after acceptance. Verify retry, no-retry, uncertain,
    and accepted results respectively, including message counts after restart.
12. Suppress a pending recipient before its next claim, then verify no submission.
    Exercise domain missing/unknown/invalid diagnostics and redacted result export.
13. Save/restore a backup in a separate profile and test missing credentials. Restore
    an older backup with later sends recorded and verify it cannot blindly replay them.
14. Complete keyboard/scaling/screen-reader checks, export diagnostics, and exit
    during bounded work; verify workers/locks/resources are released.
15. Repeat the packaged install/upgrade/restart/uninstall path as a standard user
    without the checkout or development interpreter available.
16. Run the separately authorized small live seed case, then verify provider
    acceptance and actual recipient receipt without overstating deliverability.

## Section 21: CI Workflow Design and Failure Validation

### Required workflow jobs

Keep job/check names stable for branch protection. The required merge gate must
not disappear because of path filters, conditional skips, or merge-queue events.

| Job | Trigger/platform | Inputs, permissions, and output |
| --- | --- | --- |
| `quality` | Pull request, maintained-branch push, manual; supported Python/Windows. | Locked dev tools; Ruff/Pyrefly and document/config/architecture checks; read-only repository access. |
| `tests-offline` | Same; Windows is mandatory. | Test/UI groups, fake profile, denied external app network; sanitized JUnit and coverage. Additional OS core tests do not expand advertised desktop support. |
| `package-smoke` | PR/push/manual. | Build wheel, install outside checkout, import the installed package, verify entry points and exact package files. |
| `workflow-validation` | Workflow/config changes and required aggregate gate. | Pinned actionlint/YAML/PowerShell tooling; invalid expressions/scripts fail. |
| `secrets` | PR/push plus scheduled full history. | Full ref history where needed, redacted source/index/history scan; inspect scan scope and skip limits. |
| `dependency-audit` | Dependency changes, default-branch pushes, scheduled/manual. | Locked runtime plus scheduled tool/build audit; advisory lookup failure is distinct from a clean result. |
| `static-security` | PR/push/schedule. | Configured Python analysis and CodeQL if available; review findings without blanket suppression. |
| `desktop-build` | Manual/default-branch candidate/tag. | Supported Windows, locked build tools, allowlisted artifact files; unsigned previews clearly labeled. |
| `release-verify` | Candidate/tag with required predecessor jobs. | Download actual artifact, check hashes/manifest, run packaged checks, verify version/ref/signature as applicable. |
| `required-checks` | Every protected merge path. | Aggregate the required predecessor conclusions and fail if any is failed, cancelled, or unexpectedly skipped. |

If using a merge queue, include its event and test behavior explicitly. Fork PRs
run without secrets; signing, provider tests, and publication run only in an
appropriately protected trusted context. Review workflow changes as executable
code. Pin reviewed action SHAs and verify downloaded standalone tool checksums.

### Security scan implementation detail

Implement a source/index scanner that scans a temporary export of exactly the
intended publishable files, including uncommitted changes where appropriate. It
must not recursively upload/read private local `.env` and databases just because
they share the workspace. Separately scan reachable Git history: ignored local
files do not exempt their historical copies. Discover which refs were fetched and
record those boundaries. A shallow/default-branch-only scan is not all-history proof.

Inspect historical archive/binary paths explicitly. Text secret scanners cannot
prove that a password screenshot or encrypted database is safe, and some scanners
skip large/encoded/archive data by default. Remove known sensitive historical
paths and verify their absence in addition to pattern scanning. Keep private raw
findings outside ordinary build artifacts; only publish redacted summaries.

For dependency checks, audit the locked runtime closure rather than whatever tools
happen to be installed. A planned export/audit command sequence after groups exist:

```powershell
New-Item -ItemType Directory -Force reports
uv export --locked --no-default-groups --no-emit-project --format requirements-txt --output-file reports/runtime-requirements.txt
uv run --locked --group security pip-audit --requirement reports/runtime-requirements.txt --no-deps --disable-pip
```

The export includes resolved transitive requirements; do not use `--no-deps` with
an incomplete hand-written top-level list. Verify the selected environment markers
and supported Windows/Python target are covered. Also audit resolved build/dev
groups on schedule, and inspect non-Python bundled Qt/native components through
SBOM/vendor advisory review. `pip-audit` alone is not a native-binary audit.

### Supply-chain and CI behavior

- [ ] Pin uv/Python/tool versions and review lock changes; use verified caches keyed
  by OS/Python/lock inputs. Never cache credentials, data profiles, release signing
  material, or untrusted artifacts into privileged jobs.
- [ ] Use read-only tokens by default, separate privileged jobs, explicit timeouts,
  and minimal permissions. Never execute fork-controlled code in a privileged
  `pull_request_target` path.
- [ ] CI configuration cannot silently change dependency resolution. Test stale lock
  detection and wheel contents, not just existence of `uv.lock`.
- [ ] Cancel superseded PR validation where safe, but do not cancel an active signing
  or publication transaction indiscriminately. Use distinct concurrency groups.
- [ ] Limit artifact names/paths/retention; sanitize logs and traces. Record any
  coverage upload or external service data transfer in contributor documentation.
- [ ] Ensure scheduled jobs actually execute and failures have a documented owner/
  triage process. Dependency update PRs run applicable build/UI tests before merge.

### Negative checks and hosted completion

Use a throwaway branch or test harness with safe synthetic fixtures to prove a
lint error, type error, failing/zero-collected test, stale lock, malformed workflow,
controlled secret-scanner fixture, and vulnerable locked dependency all fail their
intended gates. An actual credential is never needed for a scanner demonstration.
Test scanner/advisory service timeout and permission denial as visible failure/unknown.

Verify branch rules with a failing check and test the aggregate job on skipped,
cancelled, and failed predecessors. After editing a workflow, run a new execution
for the new commit; rerunning an old execution is not validation of changed YAML.
Record final run URLs, source SHA, inputs, tool versions, conclusions, and downloaded
artifact hashes. A dispatch receipt or green checkout job is not completion.

References: [uv CLI export options](https://docs.astral.sh/uv/reference/cli/),
[pip-audit behavior](https://github.com/pypa/pip-audit), and
[Gitleaks scan modes](https://github.com/gitleaks/gitleaks).

## Section 22: Windows Packaging, Signing, and Release Verification

### Select and stabilize the delivery format

- [ ] Evaluate one Qt-compatible packaging route, such as `pyside6-deploy`, against
  a controlled PyInstaller build. Choose and pin one for the first release with
  measured startup, size, plugin inclusion, license, and antivirus behavior.
- [ ] Prefer a diagnosable directory bundle initially if one-file extraction creates
  startup/temporary-folder problems. Final delivery can use a reviewed installer;
  document install scope, architecture, prerequisites, and user-data paths.
- [ ] Do not imply that MSIX/Store submission, automatic updates, macOS signing, or
  Linux packaging are delivered. If selected later, add their identity/signing/
  certification/upgrade gates separately before advertising support.
- [ ] Add explicit manifests/resources and a tracked packaging configuration. Include
  required Qt platform/image/TLS plugins and icons by allowlist; exclude test data,
  `.env`, databases, keys, contact lists, caches, and compiler/build credentials.

### Version and artifact identity

Use one version source in project metadata and surface it in About, CLI diagnostics,
logs, installer metadata, and a release manifest. A release manifest includes
version, commit SHA, source ref/tag, build workflow/run URL, OS/architecture,
Python/Qt/packager versions, lockfile hash, artifact filename/size/SHA-256, schema
compatibility range, and signing status. Generate dependency inventory/SBOM and
third-party notices from the actual bundled runtime, including Qt/native components.

Branch preview builds use an explicit selected branch/commit and are labeled preview.
Immutable releases use an existing `vMAJOR.MINOR.PATCH` tag matching project metadata
and pointing at the reviewed commit. A version string is not automatically a Git
ref. Validate dispatch inputs before checkout; do not claim a new version by
relabeling an old artifact. Fix the source and create a new build for each change.

### Candidate test sequence

1. Build from the reviewed source with a clean controlled build environment and
   locked tools. Run quality/offline/security gates on that same source.
2. Inspect bundle contents for forbidden files, required plugins, notices, and
   duplicated Qt/Python runtimes. Scan generated files and record scanner limitations.
3. Generate candidate metadata; if signing is required, sign the final distributable
   in a protected job. Verify the signature/timestamp and then compute final hashes.
4. Download the candidate artifact, verify its manifest/hash, and test it outside the
   repository on a clean supported Windows machine without Python/uv installed.
5. As a standard user, install, launch, configure synthetic state, run the complete
   offline journey, stop, exit, restart, restore, and inspect persisted outcomes.
6. Exercise spaces/Unicode paths, read-only install location, no credentials, no
   network, invalid settings, Windows scaling, native dialogs, and useful crash handling.
7. Test upgrade from the supported prior version, interrupted migration, schema
   incompatibility, uninstall/reinstall, and the chosen retain/remove-user-data behavior.
8. Perform only a bounded explicitly authorized live seed test if required; verify
   provider acceptance and recipient observation separately without claiming inbox
   placement or universal deliverability.
9. Verify final signature/hash/provenance and record all results against the artifact
   actually being released. Publishing may copy that verified candidate; rebuilding
   creates a new candidate requiring verification.

### Signing, publication, and rollback

Keep signing credentials outside the repository and restrict access to protected
release jobs. Unsigned internal previews are identified clearly; if public
distribution requires a signature, lack of a trusted signature blocks that release
channel. Verify timestamping/expiry and certificate identity under the chosen policy.
Check applicable Qt/dependency license obligations before distribution.

Publish release notes with supported platforms, installation, migration impact,
known limitations, checksums, and recovery instructions. Where available, generate
and verify build provenance attestations; an attestation identifies origin and
does not prove functional correctness. Inspect the hosted release asset after upload.

Rollback does not mean running an old executable against a newer unsupported schema.
Record whether the old version can open the schema; otherwise stop writes, preserve
the failed profile, and restore a verified pre-upgrade backup to a separate profile
with the matching application version. Never erase accepted/uncertain-attempt or
suppression information merely to make an old version start.

Disable automatic executable updates for the first release unless a secure update
design is explicitly implemented. A later updater needs authenticated metadata,
signature/hash verification, version/rollback policy, atomic application replacement,
active-campaign handling, and interrupted-update tests. A manual signed installer
upgrade is an acceptable documented first-release path.

References: [Qt deployment choices](https://doc.qt.io/qtforpython-6/deployment/index.html),
[pyside6-deploy](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html), and
[GitHub artifact provenance](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations).

## Section 23: Step-by-Step Execution Runbook

Execute these steps in order unless their stated prerequisites permit independent
work. Each step is a reviewable deliverable, not necessarily one commit. Stop at a
failed gate, preserve evidence, repair the issue, and rerun affected checks before
proceeding. Documentation updates accompany the step that changes behavior.

Implementation has begun; consult Execution Record 01 for delivered portions of
these steps. The four completed cleanup checkboxes in Section 03 remain historical
evidence. Do not mark an entire step complete while its required sub-gates remain open.

### E00: Freeze scope and establish the implementation baseline

- [ ] Record current branch/commit, staged/uncommitted work, root file inventory,
  protected local-file hashes, and the actual supported feature list.
- [ ] Assign owners/decisions for requirements F01-F13 and N01-N05; confirm first
  release OS/architecture, import formats, delivery channel, and provider choice.
- [ ] Prepare a synthetic profile and fault-test corpus. Keep real local files intact.
- **Gate/evidence:** requirements matrix and baseline record reviewed; no assumption
  that prior mocked imports prove a working GUI. Roll back only this step's edits.

### E01: Contain credentials and rehearse history remediation

- **Entry:** E00 baseline preserved; no rewrite in this dirty working checkout.
- [ ] Complete provider credential rotation, private recovery preparation, ref/path
  inventory, isolated history-filter rehearsal, and redacted before/after scans.
- [ ] Review/publish the coordinated rewrite when ready, verify a fresh clone, and
  document remaining fork/cache/clone handling using Section 06.
- **Gate/evidence:** no active exposed credential remains; rewritten published refs
  and known binary/archive paths verified. Preserve a restricted recovery path;
  do not silently restore tainted history as an ordinary rollback.

### E02: Establish the uv project and structured package build

- **Entry:** E00; offline foundation work may proceed while external E01 actions finish.
- [ ] Select compatible Python/Qt/tool versions, create metadata/groups/build
  configuration, scope package discovery to `src/cold_mailer`, and generate the lockfile with uv.
- [ ] Add GUI/CLI callable entry points, clean environment setup, synthetic settings
  example, and the supported dependency-install procedure.
- [ ] Build/install a wheel in a clean environment outside the checkout; verify its
  exact contents and that imports/entry points do not rely on the current directory.
- **Gate/evidence:** fresh Windows sync/build/import results and lock/build-tool
  manifest. Keep legacy requirements behavior available until parity is verified.

### E03: Configure local quality tools and the verification runner

- **Entry:** E02 builds and installs.
- [ ] Add lint/format/types/pytest/coverage/architecture/document/config checks,
  pre-commit, editor settings, tool pins, and `scripts/verify.ps1` modes.
- [ ] Configure clear maintained-code scope and the proposed thresholds; add an
  initial real regression test and enforce nonzero test collection.
- [ ] Exercise a failing native command and ensure the runner returns failure,
  preserves useful output, and restores its environment.
- **Gate/evidence:** repeatable Fast/Full tool behavior from a clean setup; no empty
  placeholder suite or blanket suppression is presented as application validation.

### E04: Bootstrap hosted CI and negative-check enforcement

- **Entry:** E03 commands and configurations are executable locally.
- [ ] Implement read-only quality/test/package/workflow jobs using the same commands,
  pinned actions/tools, full scan history where needed, and stable check names.
- [ ] Prove representative lint/test/lock/workflow failures fail hosted checks and
  fork-style runs work without secrets. Enable security jobs with findings visible.
- **Gate/evidence:** final hosted conclusions/run URLs match the reviewed commit;
  unresolved historical exposure remains failed/open rather than suppressed.

### E05: Build configuration, paths, credentials, and service bootstrap

- **Entry:** E02-E04 support tested changes.
- [ ] Implement validated settings/profiles, side-effect-free imports, per-user paths,
  OS credential-store interface/fake, redaction, and GUI/CLI dependency wiring.
- [ ] Design explicit legacy-account migration without writing real test credentials
  into the user's existing database/key; test missing-store and wrong-key behavior.
- **Gate/evidence:** F01/F02 credential/config tests and isolation checks pass;
  startup without credentials/network is usable and does not send anything.

### E06: Implement durable schema, migrations, backup, and restore

- **Entry:** E05 profile/path boundaries and credential references exist.
- [ ] Create schema/repositories, migrations, integrity checks, short transactions,
  backup/restore tooling, retention settings, and future-schema refusal.
- [ ] Test prior-schema upgrade, interrupted/failed migration, disk/permission errors,
  locked database, inconsistent backup, and credential re-entry after restore.
- **Gate/evidence:** temporary-profile restore rehearsal preserves records/invariants;
  no connection ownership ambiguity or unsupported downgrade path remains.

### E07: Implement domain IDs, state guards, and typed service interfaces

- **Entry:** E06 persistence contracts exist.
- [ ] Define commands, outcomes, events, revision/operation IDs, invariants, and
  lifecycle ownership. Split generation/approval/delivery states deliberately.
- [ ] Test forbidden transitions and races before connecting provider work. Add
  architecture checks preventing domain dependencies on Qt/concrete adapters.
- **Gate/evidence:** state/ownership tests show invalid commands cannot bypass
  guards through the CLI or direct service calls.

### E08: Implement contact validation, import/export, and suppression

- **Entry:** E06-E07 stable record/service contracts.
- [ ] Add supported readers, row diagnostics, canonicalization/deduplication policy,
  size/encoding limits, synthetic exports, and persisted suppression ingestion.
- [ ] Test corrupt/hostile/large inputs, row-level partial acceptance, duplicate
  columns, formula-safe exports, and suppression rechecks.
- **Gate/evidence:** F03/F11 import/suppression tests and a reconciled import summary
  pass without altering original input files.

### E09: Implement templates, manual drafts, revisions, and approval

- **Entry:** E07-E08 IDs and contact data are valid.
- [ ] Add restricted template context/validation, manual content, persisted drafts,
  final rendering, immutable snapshots, content hashes, and revision approval.
- [ ] Verify edits/regeneration/sender changes invalidate approval and changing
  contact-list ordering cannot swap recipient content.
- **Gate/evidence:** F04/F06 tests compare the approved final message identity/content
  with the snapshot used for transmission; unapproved content remains unsendable.

### E10: Replace and validate the AI adapter

- **Entry:** E05 configuration and E09 validated draft/approval contracts.
- [ ] Migrate to the maintained SDK, preserving the selected model, with deadlines,
  bounded retries/budgets, minimal personalization data, and validated outputs.
- [ ] Cover missing/invalid credentials, quota/rate-limit, blocked/empty/partial
  responses, placeholder text, cancellation, and untrusted contact instructions.
- [ ] Run the synthetic semantic evaluation set; isolate any live evaluation by
  account/recipient/data/budget and record its model/prompt revision.
- **Gate/evidence:** F05 passes; no AI failure can mark a message approved or bypass
  manual review, and optional manual-only authoring remains available.

### E11: Repair SMTP composition, TLS, cleanup, and outcome classification

- **Entry:** E05 settings and E09 immutable message contract.
- [ ] Implement explicit transport modes, verified certificates, envelope/header
  validation, MIME metadata, timeouts, and reliable resource cleanup.
- [ ] Exercise local protocol/TLS fixtures for auth errors, recipient refusals,
  temporary/permanent responses, loss during DATA, and QUIT after acceptance.
- **Gate/evidence:** protocol transcripts and F08 tests demonstrate correct
  classifications; accepted mail never becomes retryable due to cleanup alone.

### E12: Integrate the persistent campaign engine and recovery

- **Entry:** E06-E11 contracts/adapters verified independently.
- [ ] Add atomic claiming, serial sending, account health/limits, bounded retries,
  stop handling, suppression checks, run accounting, and restart reconciliation.
- [ ] Test duplicate start, second process/profile owner, stale events, zero eligible
  messages, mixed failures, and termination at send/journal boundaries.
- **Gate/evidence:** F07-F11 crash/cancellation tests and a fake-provider full
  campaign pass. No accepted/uncertain attempt is automatically replayed.

### E13: Deliver the headless validation and diagnostics interface

- **Entry:** E12 shared services are reliable without Qt.
- [ ] Provide validate/import/plan/dry-run/run/recover/diagnostic commands with clear
  help, structured summaries, bounded seed mode, and documented exit codes.
- [ ] Test Ctrl+C, invalid options/configuration, redirected output, alternate working
  directory, and command injection/header-input boundaries.
- [ ] Update current CLI documentation and remove inherited instructions that no
  longer match actual configuration or safety behavior.
- **Gate/evidence:** F12 CLI/service parity tests and an offline complete journey
  persist the expected data without live provider calls.

### E14: Specify the PySide6 screens and build the application shell

- **Entry:** E07 service contracts stable; E13 gives a working engine reference.
- [ ] Review wireframes/state maps, keyboard/accessibility expectations, performance
  baseline, navigation, and confirmation/recovery wording.
- [ ] Add Qt resources, model/view tables, controllers, app lifecycle, worker owners,
  and queued typed signals with testable service injection.
- **Gate/evidence:** shell UI tests pass with synthetic profiles; no network/storage
  work blocks the GUI and no worker directly mutates widgets.

### E15: Connect complete GUI workflows and offline end-to-end tests

- **Entry:** E14 shell and E12-E13 service behavior exist.
- [ ] Implement sender setup, contacts, drafts, generation, review, approval, dry-run,
  send monitor, stop/recovery, suppression, and diagnostics screens.
- [ ] Cover unsaved edits, navigation during work, stale results, close/restart,
  missing credentials, offline state, and partial failures.
- **Gate/evidence:** F01-F12 applicable UI/offline journeys verify message bytes,
  SQLite outcomes, visible counts, and absence of extra sends across restart.

### E16: Run the bounded live contract and seed verification

- **Entry:** E15 offline journey passes; rotated test credentials and explicit
  recipient/account authorization are available. Otherwise keep this gate open.
- [ ] Test selected AI model response/error behavior, SMTP account/TLS configuration,
  and a small approved seed campaign with fixed limits and saved revisions.
- [ ] Inspect provider outcomes and recipient receipt separately; keep any real
  message/recipient details out of public artifacts and routine CI logs.
- **Gate/evidence:** redacted live contract/seed results and observed limitations.
  A failed live check returns work to the relevant adapter/service step.

### E17: Complete faults, accessibility, performance, and security review

- **Entry:** E15 full offline app and E16 integration findings addressed.
- [ ] Execute the full crash/fault matrix, multi-instance checks, long-running fake
  soak, high-DPI/keyboard/Narrator review, and measured performance budgets.
- [ ] Review data retention, prompt/template/input trust boundaries, logging, export,
  secret storage, and runtime/native dependency findings.
- **Gate/evidence:** F13/N02-N05 results, coverage reports, benchmark environment,
  unresolved issues, and acceptance decisions recorded; no critical defect waived.

### E18: Build the first controlled Windows desktop candidate

- **Entry:** E17 first-release behavior passes; packaging tool/channel decision made.
- [ ] Create explicit packaging/resource configuration, lock build tools, generate
  version/manifest/SBOM/notices, and inspect the candidate contents.
- [ ] Verify installed wheel and executable entry points agree about module/resource
  resolution and do not embed root private files.
- **Gate/evidence:** candidate artifact hash/tool manifest and bundle inspection
  pass; this is a candidate, not a publicly verified production release.

### E19: Verify clean installation, upgrade, data migration, and rollback

- **Entry:** download the exact E18 candidate and verify its hash.
- [ ] On clean supported Windows without Python/uv, test first launch, standard-user
  paths, complete offline workflow, exit/restart, backup/restore, and diagnostics.
- [ ] Test supported previous-version upgrade and interruption, schema mismatch,
  credential re-entry, uninstall/reinstall, and explicit data-retention behavior.
- [ ] Rehearse compatible rollback or backup-based recovery in a separate profile.
- **Gate/evidence:** packaged F01/F10/F13/N01/N05 acceptance and migration/rollback
  records match the actual artifact; destructive failure preserves the source data.

### E20: Finalize CI/security enforcement and workflow failure behavior

- **Entry:** E18-E19 executable build/verification steps are available.
- [ ] Integrate packaging/artifact checks into trusted CI and finish required checks,
  full-history/source/native dependency scan scope, scheduled jobs, and update tooling.
- [ ] Exercise the negative-check matrix, unexpected skips/cancellations, merge
  protection, scanner outages, and trusted/untrusted permission boundaries.
- **Gate/evidence:** hosted results for the reviewed commit and demonstrated merge
  blocking; no suppressed unresolved history exposure or vulnerable dependency.

### E21: Produce and validate the release candidate

- **Entry:** E16-E20 gates closed and first-release support/channel decisions fixed.
- [ ] Validate version/tag/source SHA, build from controlled inputs, sign if required,
  generate final checksums/provenance, and download/verify the candidate again.
- [ ] Re-run the required candidate/packaged checks on the final bytes and complete
  documentation, known issues, installation, migration, and recovery instructions.
- [ ] Establish maintenance/incident owners and rehearse Section 24 before public
  distribution. E23 repeats and sustains those responsibilities after publication.
- **Gate/evidence:** release evidence bundle identifies exactly one candidate and
  all required conclusions; do not rebuild different bytes after approval.

### E22: Publish and verify the distributed release

- **Entry:** E21 verified candidate and intended publication authorization.
- [ ] Publish the verified artifact, manifest, checksums, notices, and release notes
  to the selected channel; do not publish real data or private scan outputs.
- [ ] Download from the actual distribution location, verify identity/hash/signature,
  and execute the minimum clean-install smoke path from those distributed bytes.
- **Gate/evidence:** hosted asset URLs, final hashes, installation result, and source
  identity match. On discrepancy, stop distribution and investigate/revoke as needed.

### E23: Establish maintenance, recovery drills, and lifecycle ownership

- **Entry:** E22 distributed release is verified, or rehearse before public release.
- [ ] Assign owners/cadence for scheduled scans, dependency/model changes, backups,
  incident response, user reports, signing expiry, and support documentation.
- [ ] Rehearse an uncertain-send incident, compromised credential, failed upgrade,
  and restore with inaccessible user-bound credentials using synthetic profiles.
- **Gate/evidence:** Section 24 readiness checklist and incident/maintenance records
  are complete; ongoing work has an owner instead of being marked permanently done.

## Section 24: Operations, Incident Response, and Final Readiness

### Operator documentation deliverables

Keep an accurate README entry point with setup and first launch, supported
platforms, synthetic quick start, sender/model setup, import rules, review/approval,
dry run, bounded seed tests, run/stop/recover behavior, outcome definitions,
suppression, backup/restore, diagnostics, upgrade/uninstall, and known limitations.
Document the CLI exit-code mapping and configuration reference generated from the
actual schema. Remove conflicting inherited setup and packaging claims as each
replacement is delivered; do not tell users planned commands already work.

Developer documentation must include bootstrap, architecture boundaries, local
verification modes, fixtures, live-test opt-in, test-marker meaning, dependency/tool
updates, CI triggers/permissions, build inputs, signing/publication, and evidence
locations. This plan can remain the implementation reference; user help should
not require reading the whole plan to operate the app.

### Maintenance schedule and ownership

| Cadence/event | Required action |
| --- | --- |
| Every change | Appropriate local/hosted checks, requirement mapping, docs/migration review, and staged-secret scan. |
| Scheduled weekly baseline | Dependency/security scans, failed-workflow triage, provider/model deprecation review, and expiring exception checks. |
| Every release | Clean build/install, bundled dependency/license review, signature/version/source validation, upgrade/recovery checks, and evidence retention. |
| Periodic recovery drill | Restore synthetic backup, simulate crash/uncertain send, and verify recovery instructions with a different test Windows profile. |
| Dependency/provider breaking change | Isolated upgrade, lock regeneration, adapter/evaluation/UI/packaging regression tests, and explicit selected-model decision. |
| Signing compromise/credential exposure | Stop privileged distribution/sending as applicable, revoke/rotate, investigate scope, and publish a verified replacement only after remediation. |

Choose named owners and precise scheduled days/retention durations during E23;
do not treat an unassigned recurring checklist as operational coverage. Telemetry
is off unless deliberately designed and disclosed; local diagnostic export is
sufficient initially. Do not collect message bodies or contact lists as monitoring.

### Incident response procedure

1. Stop new sends/publication when the outcome could be unsafe; preserve the
   profile, accepted/uncertain attempt records, version, and redacted diagnostics.
2. Classify credential exposure, provider outage/quota, incorrect recipient/content,
   duplicate/uncertain send, data corruption, or release/update failure.
3. Contain the affected account/version without deleting evidence or automatically
   replaying the campaign. Rotate credentials or revoke a release where applicable.
4. Reconcile server acceptance with persisted attempts and available provider data;
   distinguish unknown from confirmed failure. Never infer that lack of a log means
   the recipient did not receive the message.
5. Repair in a synthetic reproduction, run targeted/full relevant checks, and
   rehearse restore/rollback. Preserve user data before any migration or reset.
6. Release/communicate the verified remedy through the authorized channel, record
   impact and limitations, and add a regression test plus a prevention action.

### Evidence record template

For each gate record: step and requirement IDs; owner/date; source commit and
working-tree state; OS/Python/Qt/tool versions; configuration profile without secret
values; exact commands and test scope/counts; pass/fail/skip/unknown conclusions;
hosted run/artifact locations; final hashes/signing state; limitations; and next
action. Use sanitized summaries in repository documentation and access-controlled
raw evidence only where necessary. Distinguish source-level, mocked, protocol,
live-provider, and packaged verification.

### Final first-release readiness checklist

- [ ] F01-F13 and N01-N05 are implemented with linked tests/evidence or explicitly
  descoped before release; required first-release behavior has no unresolved blocker.
- [ ] Structured package architecture, supported OS/toolchain, configuration, and provider
  model decisions match the actual implementation and installed app.
- [ ] Exposed credentials are rotated, intended published history is remediated,
  and current source/artifacts have no unresolved secret findings.
- [ ] Fast/Full/Security/Release checks execute, meaningful tests collect, thresholds
  are enforced, and negative-check evidence proves defects block the intended path.
- [ ] Real temporary database/TLS/worker tests complement mocks; complete UI/CLI
  journeys and crash/recovery boundaries pass without replaying accepted/uncertain mail.
- [ ] Live contract/seed verification is bounded, authorized, and recorded, with
  SMTP acceptance, recipient observation, and delivery limitations kept distinct.
- [ ] Storage migration, retention, restore, credential loss, multi-instance behavior,
  and compatible rollback are verified without destroying protected local data.
- [ ] Accessibility, responsiveness, large-contact capacity, and soak budgets are
  measured on the stated supported baseline, with any accepted tradeoff documented.
- [ ] The downloaded final artifact matches the reviewed source/version/manifest,
  required signature, checksums, bundled dependency inventory, and notices.
- [ ] A standard user can install, configure, complete a campaign, stop/recover,
  upgrade, export diagnostics, and uninstall using accurate documentation.
- [ ] Hosted required checks and publication/artifact verification are complete for
  the actual release revision; no merely dispatched or unrelated old run is counted.
- [ ] Known limitations, incident/recovery procedures, maintenance owners, scheduled
  scans, and support/security-reporting paths are established.

Completion means a reproducibly built, tested, safely operable desktop application
with traceable evidence and a maintenance process. It does not mean every possible
future platform, integration, or unknown vulnerability has been covered.
