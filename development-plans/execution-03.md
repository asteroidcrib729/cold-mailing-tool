# Execution 03: Reviewed Imports, Run Boundaries, and Recovery

Date: 2026-10-20 (Asia/Karachi).

This continues [Plan 02](development-plan-02.md) and supersedes the current-status
and next-work tables in [Execution 02](execution-02.md). Earlier evidence remains
historical. The owner authorized further autonomous local implementation; commits,
pushes, live messages, credential rotation, and destructive history rewriting
remain outside this iteration.

Subsequent owner instructions authorized iterative commits/pushes, historical
remediation, and bounded live AI tests. See the [remediation record](security-remediation-01.md)
and [Live Testing 01](live-testing-01.md) for newer evidence. Verification figures
below describe this implementation checkpoint; they do not claim current live
generation or installer acceptance.

## Delivered behavior

| Area / requirements | Implementation | Practical boundary |
| --- | --- | --- |
| Reviewed imports; FI-02, R02-07 | CSV/XLSX header and sample preview, explicit column mapping, named reusable mapping profiles, row diagnostics, and source SHA-256 recheck before import. File limits are 10 MiB input, 50 MiB expanded workbook, 10,000 data rows, and 100 header columns. | No silent field replacement or merge. Changed source files must be previewed again. Formula cells are data; no formula execution. |
| Provenance; FI-13 | Atomic import-batch records retain source label/hash, UTC import time, operator note, reviewed flag, and links to individual recipients. Reimports add provenance without overwriting contact details. Campaign tools shows the records. | These record operator statements; they do not establish legal permission. Collection-date fields, review filters, and provenance export remain open. |
| Frozen audiences; FI-04, R02-03/07 | GUI sending freezes the visible recipient IDs and their current revision/approval fingerprints after confirmation. Membership is immutable; claim rechecks the snapshot in the same transaction as admission. Durable run IDs and summaries record outcomes. | Later imports, approvals, edits, and reapprovals cannot expand that run. A completed run cannot be reused. Rich attribute segments remain open. |
| Sending windows; FI-09, R02-05/07 | Opt-in IANA timezone, weekdays, start/end times, overnight windows, and optional explicit per-contact timezone. UTC-to-local admission and next-time preview account for DST transitions. | An admission gate, not unattended scheduling. Missing contact timezone holds when that mode is selected. No address-based guesses, holidays, or catch-up bursts. |
| Generation budgets; FI-22, R02-06/07 | Atomic durable request reservations enforce per-operation and rolling-24-hour ceilings across serial, parallel, and candidate generation. Model name, brief hash, source revision, and request result are recorded. Optional user-supplied planning cost is displayed. | Failed/interrupted requests count conservatively. These are request limits and estimates, not token metering or a billing/spend guarantee. |
| Revision recovery; R02-03/04 | Side-by-side subject/body revision comparison, explicit restore into a new unapproved draft, and compare-and-swap conflict checks. | Old revisions and transport snapshots remain unchanged. Saving/provider operations and dirty editors block conflicting restoration. |
| Offline feedback; FI-10/16 | Bounded local EML parsing, plain-text review, reply/opt-out/note classification, source-hash deduplication, and durable feedback/audit rows. Reply/opt-out linking requires both outbound Message-ID references and matching recipient From. Confirmed opt-out atomically suppresses that address and holds pending messages. | No inbox connection, synchronization, or authentication claim. Unmatched evidence can only become an explicitly chosen note. HTML and attachments are not rendered. |
| Reports; FI-16 | Campaign tools shows durable transport outcome totals, operator-recorded feedback counts, request admissions, and recent run summaries. | SMTP acceptance, replies, and delivery are distinct. Delivery remains unknown without provider evidence. Date-scoped report exports remain open. |
| Workspace recovery; FI-14/17 | GUI plain/encrypted backup restoration into a new empty workspace; restores mark pending messages and interrupted jobs as held. Open a separate existing/new workspace in its own process with isolated profile/credential namespaces. | Never overwrite the current profile. Source launches use isolated Python mode and strip inherited development API-key variables. No shared suppression policy is implied. |
| Autosave; R02-04 | Brief/template and recipient drafts use the bounded background saver. Requested navigation replays after acknowledgement. Manual Save/Discard/Cancel preserves correct recipient/campaign identity; failed writes retain editor text. | No plaintext credentials enter autosave. General editor undo/recovery journals and full-disk power-loss drills remain open. |
| Responsive history; R02-02/06 | Search uses one read-only worker and one coalesced pending query, discarding stale results. Readers do not hold the Store writer mutex; SQL VM work has a 500 ms budget and lock wait is bounded. Local timezone display and inclusive local-date filtering retain UTC CSV timestamps. CLI offers offset-aware `--since` / `--until`. | Very broad/contended searches can stop with a visible retry/narrow-search message. Matching CSV export runs in the foreground-operation worker and publishes only after successful completion. Export pages reflect records when read, not a database-wide audit snapshot. |
| Appearance and lifecycle; FI-20, R02-01/06 | Persisted contrast theme, consistent date/time controls, sufficient date/theme text widths, and cached identical global theme application. Weak controller callbacks and Qt slots remove avoidable widget ownership cycles. | Font scaling, density, screen-reader acceptance, and formal frame-time budgets remain open. |

## Storage and safety contracts

Schema version **3** upgrades v1 through v2, retaining the existing pre-upgrade
backup/integrity contract. New tables cover import batches, source links, frozen
runs/membership, generation requests, feedback, and audit events. Historical v1
attempt content remains explicitly unknown. Run membership rejects updates/deletes.
Restoring supported older schemas is permitted; normal startup migrates them before
use. Recovery never automatically replays a send or provider request.

Serial generation now checks the campaign brief after the provider response,
matching the parallel/candidate protection. A changed brief or draft makes the
result stale; cancellation preserves the draft. Reservations remain counted.
History exports write to a temporary file and publish exclusively after success;
cancellation/read failure removes the partial file. Existing destinations remain
protected. Exported cells retain spreadsheet formula protection.

SQLite remains in rollback-journal mode. The bundled runtime patch prerequisite
for WAL is still open; neither a DLL replacement nor WAL activation is justified
by these tests. Profile credentials remain in OS storage and database backups do
not contain them. Real legacy root files are not used as fixtures.

## Verification record

The final source verifier passed **173 offline tests**, with **91.68% combined
branch-inclusive coverage**. Critical-module coverage is domain models 100%,
campaign engine 96.81%, storage 98.34%, and SMTP 97.26%; the existing 90% overall
and 95% critical thresholds were retained. Ruff, formatting, Pyrefly, repository
boundaries/document links, actionlint, and the publishable snapshot scan pass.
The snapshot scan has zero findings; Bandit over source/tooling has zero findings.
The online locked runtime audit reports 42 dependencies and zero known package
advisories at audit time. This does not close the native SQLite runtime gate.
The separate historical Git scan still reports **six findings in three commits**;
no historical exposure was suppressed or rewritten.

Native captures cover all five tabs in light/dark/contrast modes at effective Qt
device-pixel ratios 1, 2, and 4, plus a 1000-by-650 logical-pixel window. Each run
checks visible button heights. Inspection found date/theme text clipping, corrected
before the final build. These are native layout checks, not a screen-reader or
frame-time certification. The repeated full suite completes without the earlier
native Qt termination. The frozen application also launches and saves a snapshot
using a separate synthetic profile. Two optional PyInstaller `pycparser.lextab` /
`yacctab` hidden-import warnings remain; they do not prevent that smoke launch.

Both preview installers rebuild successfully. MakeAppx validates the unsigned
MSIX. The artifact verifier checks exact current-source fingerprints, preview
identity/version, frozen executable/native SQLite/SVG payload bytes, and installer
checksums. The rebuilt EXE passes installation, installed-app smoke, same-version
reinstallation, another smoke, and uninstallation on this Windows machine; the
synthetic profile hash is preserved. The initial sandboxed installer attempt
returned exit code 4 before creating the installation directory. The authorized
retry with access to per-user installer registration/shortcuts passes. No trust
certificate is installed. Hosted CI, signed MSIX installation, clean-machine
upgrades, and rollback remain separate open gates.

The source archive includes the packaging recipes and GitHub workflows so the
build context accompanies the application, tests, and tooling. Wheel/archive
verification checks exact package source/assets and private-file exclusions;
an isolated installed-wheel smoke verifies the installed entry point. Local
evidence is retained under ignored `reports/implementation03-*`,
`reports/ui-03-*`, `reports/windows-artifact-verification.json`, and
`reports/installer-smoke.json`; preview binaries/checksums are in `dist/installers/`.

Fresh SHA-256 comparisons confirm the four private root files, Git index, and
HEAD remain unchanged. No commit, push, workflow dispatch, live transmission,
real-profile migration, or history rewrite occurred.

New checks cover import file drift, atomic provenance, immutable run scope,
late approval races, persistent budgets, DST gaps/folds, overnight weekdays,
operator feedback deduplication/suppression, revision conflicts, autosave failure
and navigation replay, workspace subprocess isolation, cancelled exports,
timezone-aware history, coalesced searches, and widget destruction on the GUI thread.

## Remaining local implementation

These items remain authorized and do not inherently require owner input. They
are subsequent engineering work, not external blockers or completed acceptance:

1. General bounded job coordinator: fair admission, per-job cancellation, queue
   saturation, writer contention, deterministic shutdown, and measured latency.
   Current concurrency remains two AI workers, serialized SMTP, one draft saver,
   and one independent read-only history worker.
2. Structured segments/tags, reversible field-by-field contact merge review,
   collection-date/review-filter/provenance exports, and workspace administration.
3. Allowlisted local action recipes, richer setup navigation, variable previews,
   review-hint dismissals, and generation provenance presentation.
4. Date-scoped aggregate report exports, stable point-in-time CSV export snapshots,
   token/usage accounting, and optional holiday calendars.
5. Font scaling/density, keyboard and assistive-technology audits, bounded-memory
   and large-dataset benchmarks, sleep/resume and disk-full/power-loss drills.
6. Reviewed attachment support requires a complete content/hash/approval/backup
   contract before MIME changes; no attachment implementation is implied here.
7. Typed configuration repair, retention/purge policy with replay evidence, and
   a verified compatible patched native runtime before enabling WAL.

## Work requiring the owner or external evidence

| Gate | Needed participation | Next concrete action |
| --- | --- | --- |
| Exposed credentials and Git history | Owner confirmed revocation/rotation and approved the eight-branch rewrite and local obsolete-object cleanup. Fresh remote/local scans pass. | [Remediation 01](security-remediation-01.md) records the completed work; old GitHub cached-commit access and other clones remain external follow-up. |
| Hosted GitHub Actions | Development, security and CodeQL checks pass on the rewritten application checkpoint. | Hosted EXE/MSIX acceptance remains separate: dispatch the selected branch with blank release tag for a preview, or an existing matching release tag. Verify downloaded artifacts/checksums. |
| MSIX signing and update trust | Publisher/Store identity, signing certificate/key custody, channel policy, and authorized trust configuration. | Supply/choose the release identity; keep unsigned development identity separate. No fabricated certificate or silent trust installation. |
| Live provider acceptance | Explicit model/account choice, credentials, authorized seed recipients, and live-test authorization. | Rehearse in demo, then run a bounded seed test and reconcile actual provider evidence. |
| Inbox integration | Chosen provider, minimal OAuth scope, mailbox authorization, and retention policy. | Keep offline EML feedback as the manual fallback until the account flow is reviewed. |
| Clean-machine release | Isolated Windows VM/user and release/rollback acceptance choices. | Install, upgrade, restore, and uninstall without developer tools; verify credential/profile continuity and MSIX behavior. |

Plan 02 remains active. [Features and improvements](features-and-improvements.md)
retains the full acceptance criteria; partial delivery must not close them wholesale.

Implementation references: Python's [timezone support](https://docs.python.org/3.14/library/zoneinfo.html)
and [email parser](https://docs.python.org/3.14/library/email.parser.html). The app
uses explicit timezones and local file review; neither facility establishes inbox
authorization, sender authenticity, or message delivery.
