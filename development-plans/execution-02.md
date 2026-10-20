# Development Plan 02: Implementation Evidence

Dates: 2026-10-19–20 (Asia/Karachi). Status: first implementation tranche delivered;
remaining acceptance and feature work stays open.

The owner authorized autonomous implementation of [Plan 02](development-plan-02.md)
and [the additional features](features-and-improvements.md). No commits or pushes
are made. Existing staged changes, private root files, and Git history are preserved.

## Implemented behavior

| Requirement | Current implementation | Remaining acceptance |
| --- | --- | --- |
| R02-01 scrolling | Reusable 150 ms eased coarse-wheel scrolling; native pixel wheel passthrough; keyboard interruption; unfocused choice/numeric wheel guards; smooth/reduced-motion toggles persisted per profile. | Broader touchpad/nested-view native testing, automatic OS reduced-motion detection, measured latency. |
| R02-02 persistence | Transactional v1-to-v2 migration with a pre-upgrade SQLite backup; nullable legacy facts; draft UTC microsecond timestamps; append-only revisions; immutable attempt sender, recipient, subject, body, revision, and content hash captured before SMTP. History tab/CLI search, outcome filters, pagination, formula-protected CSV export, UTC labels. | Date-range and local-timezone filters, large-history benchmarks, richer reconciliation events and retention policy. Existing attempts without snapshots remain unknown. |
| R02-03 individual content | Every recipient retains independent subject/body/instructions. Selected regeneration returns a candidate for explicit acceptance; current content survives rejected/stale candidates. Saved revisions and approximate narrow/wide reading previews are available. | Generation provenance, revision comparison/restoration UX and full instruction/campaign generation-token lifecycle. |
| R02-04 autosave | On by default; 800 ms debounce, five-second maximum continuous-edit timer; one background save at a time; stable IDs and revision checks; incomplete drafts supported; saving/saved/error states; settings toggle; navigation holds selection while saving; close flushes via the event loop. First edit serializes with claim and durably removes approval. Secrets are excluded. | Fault injection for disconnect/full/read-only storage, pending-navigation replay, campaign-brief autosave, crash-recovery editor journal, full accessibility review. First-edit registration is a short synchronous transaction. |
| R02-05 pacing | A sampled `[0,1)` second additive jitter is persisted once after each outcome; waits start after completion and survive restart; toggle; longer account intervals win; real SMTP has a five-second application floor, fake adapters may use zero. Cancellation interrupts waits. | Explicit provider cooldowns, quiet-hour/timezone scheduling, richer policy/run snapshots, health holds, no catch-up bursts under clock changes. |
| R02-06 concurrency | Stateless AI adapters run at most two requests with a bounded Python 3.14 map buffer; SMTP remains serialized; background autosave has one pending write; each SQL operation owns a connection; Store serializes its short transactions. Settings/history remain available during provider jobs. Native Qt thread cleanup still uses zero-timeout join polling. | General fair multi-job coordinator, priority admission/reserved safety capacity, progress coalescing and stress/performance budgets. Existing profile operation lock still prevents overlapping bulk generation and transmission. |
| R02-08/R02-09 packaging | EXE/MSIX preview workflow, immutable ref resolver, version/tag validation, pinned verified Inno compiler, per-user EXE definition, SDK MakeAppx schema validation, generated logo assets, checksums/manifests, EXE install/reinstall/uninstall smoke. | Hosted artifacts, clean-machine upgrades/rollback, native runtime patch gate, production signing identities/custody, signed MSIX installation and Store policy. |

The SQLite runtime remains in rollback journal mode. WAL is deliberately gated on
verification of a patched bundled SQLite version; adding threads does not enable WAL.
SMTP acceptance remains distinct from inbox delivery. Random delays do not bypass
provider limits or establish that a message will avoid filtering.

## Local artifacts and launch commands

The final preview payload, EXE installer, unsigned MSIX, checksums, source manifest,
source-resolution metadata and verification evidence are under `dist/installers/`.
The standalone frozen directory is `dist/desktop/ColdMailer/`; its `_internal/`
directory must stay beside `ColdMailer.exe`. These generated files are ignored by
Git. The source build is deliberately marked dirty/unsigned because this work is
uncommitted; the old HEAD alone does not identify the new implementation. The
source fingerprints in the manifest identify the current application files.

```powershell
uv --cache-dir .uv-cache run --locked cold-mailer-desktop
uv --cache-dir .uv-cache run --locked cold-mailer-desktop --demo
```

The installer files are `ColdMailer-0.1.0-x64-setup.exe` and
`ColdMailer-0.1.0-x64-unsigned.msix`. See
[the packaging guide](../packaging/windows/README.md) for workflow inputs,
tool verification, preview identity, and signing/install limitations.

## Additional feature delivery

Historical status from this tranche. [Execution 03](execution-03.md) supersedes
this table and the next-execution sequence below with the subsequent implementation.

| Feature | Status and implemented surface | Next work |
| --- | --- | --- |
| FI-01 demo | Implemented synthetic temporary workspace, fake AI/SMTP and visible no-transmission banner; live toggle is disabled. Launch with `cold-mailer-desktop --demo`. | Native packaged rehearsal acceptance. |
| FI-02 import mapping | Pending. | Mapping/preview UI, saved mappings and bounded importer tests. |
| FI-03 blueprints | Versioned immutable recipe rows; save and create via Ctrl+K; recipes are reviewed before creating an empty, unapproved campaign. | Change notes, provenance/schema and archive management. |
| FI-04 views/segments | Saved recipient text filters persist; visible explanation says sending uses the campaign's approved recipients. | Attribute rules, frozen selected run IDs and segment management. |
| FI-05 commands | Ctrl+K palette; Ctrl+S saves, Ctrl+F searches, F1 lists shortcuts. Palette excludes transmission. | Full searchable action registry and keyboard-only accessibility audit. |
| FI-06 previews | Approximate plain-text wrapping at 40/72 characters with unchanged saved content. | Native reading/accessibility checks. |
| FI-07 review | Deterministic missing subject, long subject/body, unbroken text, unresolved variables and strong-claim hints. | Claim provenance, dismissals and model-advice evaluation. Rules do not verify facts. |
| FI-08 setup | Reopenable checklist links work stages and demo launch guidance. | Resumable navigation and credential-readiness diagnostics. |
| FI-09 quiet hours | Pending. | Reviewed timezone/DST policy and scheduler integration. |
| FI-10 reply triage | Pending. | Offline parser, account authorization and read-only integration. |
| FI-11 variables | Contact-field dictionary and template insertion via Ctrl+K; existing strict renderer catches missing variables. | Inline previews and richer missing-field diagnostics. |
| FI-12 contact merge | Pending. | Explicit conflict review and immutable contact identity history. |
| FI-13 contact provenance | Pending. | Source/permission fields and operator review UX. |
| FI-14 workspaces | Existing explicit `--data-dir` isolates database, profile lock and credentials; demo uses temporary state. | Profile switcher and branded multi-workspace management. |
| FI-15 macros | Pending. | Safe allowlisted action recipes; sending must remain explicit. |
| FI-16 reports | History shows honest transport outcomes and exact attempts. | Aggregates, reply/feedback ingestion and exports without delivery claims. |
| FI-17 encrypted backup | Versioned AES-256-GCM envelope; random salt/nonce; bounded scrypt KDF; passphrase confirmation in GUI; CLI restore; authenticated tamper failure; new destination only. Database backups exclude OS passwords/API keys. | GUI restore wizard, recovery drills, independent format/security review and lifecycle documentation. |
| FI-18 support bundles | Exact local preview and exclusive-create ZIP containing allowlisted runtime/tool/version diagnostics. Paths, contacts, content, logs and credentials are excluded. Nothing is uploaded. | Owner-approved optional extra diagnostics. |
| FI-19 updates | Pending. | Trusted release identity/key/channel and verification/rollback design; no invented trust roots. |
| FI-20 accessibility | Existing light/dark/system themes plus scrolling/reduced-motion preferences. | Font scaling, density, contrast and assistive-technology acceptance. |
| FI-21 repair | Read-only doctor/checklist available. | Typed reversible configuration repair actions. |
| FI-22 budgets | Pending. | Request/token budgets and operator-provided pricing estimates. |
| FI-23 attachments | Pending. | Reviewed attachment hashing/snapshot/approval integration before any MIME changes. |
| FI-24 doctor | CLI `doctor` and Settings dialog report Python, Qt, SQLite, WAL patch status and tool availability; no network probes or secrets. | More detailed build/installed-runtime diagnostics. |

All remaining Plan 01 carryovers remain open in Plan 02. In particular, exposed
historical credentials require rotation and coordinated history remediation;
no secret-history rewrite or force-push occurs in this phase.

## Verification

The final source suite passes **129 offline tests**, with **91.79% branch-inclusive
coverage**. Critical coverage is domain 100%, campaign engine 97.62%, persistence
98.28%, and SMTP 97.26%. Existing behavior and the new features pass the same
repository coverage gates; thresholds were not lowered.

- `scripts/verify.ps1 -Mode Full`: lockfile, Ruff lint/format, Pyrefly, package/import
  boundaries, Markdown links, actionlint, offline tests, coverage gates, publishable
  snapshot secret scan: passed. The snapshot scan reports zero findings.
- Bandit over `src` and `scripts`: zero findings. Narrow documented exceptions cover
  local fixed-argument Git calls, locally generated manifest parsing, and non-secret
  pacing randomness. No general scanner suppression was introduced.
- `pip-audit` with exported locked hashes: 42 runtime dependencies, zero known
  advisories at audit time. This does not establish that bundled native libraries
  have no vulnerabilities; the SQLite WAL patch gate remains open.
- Full Git history Gitleaks scan: three commits scanned, six existing findings.
  Rotation/history remediation remains open; findings were not suppressed and no
  history was rewritten.
- Wheel and source archive built offline. Package contents, exact source equality,
  and private-file exclusion checks pass. The wheel was force-reinstalled into an
  isolated environment, its installed import path verified, its read-only doctor
  executed, and its desktop smoke/snapshot completed successfully.
- Native Windows captures cover all four tabs in both themes at 1280×860 logical
  pixels with 100% and 200% effective scaling, plus 1000×650 small-window captures.
  Native inspection found an editor overlap; the layout minimum constraint fixes it,
  and a regression test verifies field separation and usable body height. Buttons
  retain usable dimensions; small windows scroll the complete editor.
- Frozen PyInstaller directory built and launched with an isolated profile and
  snapshot. Source fingerprints match all 42 packaged application source/assets.
  Two optional `pycparser.lextab`/`yacctab` hook warnings remain; smoke launches pass.
- Inno Setup 6.7.3 was downloaded using the official release's pinned SHA-256 and
  verified Windows publisher signature. EXE installer compilation passed. Windows
  SDK MakeAppx accepted the unsigned MSIX schema/package. Artifact verification
  checks preview identity/version, exact executable/SQLite/SVG payload bytes,
  private-file exclusion, source fingerprints and both installer checksums.
- The actual EXE installer passed local isolated installation, installed-app smoke,
  same-version reinstallation, another installed-app smoke, and uninstallation.
  The synthetic SQLite profile's SHA-256 remained unchanged. This verifies the
  per-user preview installer on the current Windows machine; it does not establish
  a clean-machine upgrade, rollback, or hosted result. Hosted workflow runs and
  signed MSIX installation remain unverified. This is an unsigned development preview.
- Fresh SHA-256 checks confirm the four preserved private root files, staging
  index and Git HEAD are unchanged. No commit, push, dispatch, live email, credential
  rotation, trust-certificate installation or real-profile migration was performed.

Meaningful new tests cover v1 preservation/backup, unknown legacy snapshots,
immutable history/revisions, first-keystroke/claim races, additive persisted timing,
account-limit increases, cancellation, bounded generation, stale/failing generation,
autosave recovery/navigation/restart, demo isolation, formula-safe exports,
encrypted-backup roundtrip/tamper/wrong-key rejection, and diagnostic allowlists.

## Next execution sequence

1. Continue the remaining fault, performance and release acceptance checks; retain
   the passing local checks above as the baseline for subsequent changes.
2. Address remaining autosave/navigation/fault and runtime patch gates before
   introducing a general multi-job coordinator or WAL.
3. Add import mapping, contact provenance/merge review and frozen run segments.
4. Add quiet-hours/timezone scheduling and health/provider cooldown policy.
5. Add generation budgets, provenance, reports and safe local recipes.
6. Add reply-triage adapters only with explicit account authorization; add attachment
   support only after snapshot/approval tests cover every content change.
7. Establish signing/update trust identities, push only when requested, then run
   hosted EXE/MSIX builds and record clean-machine install/upgrade/rollback evidence.
