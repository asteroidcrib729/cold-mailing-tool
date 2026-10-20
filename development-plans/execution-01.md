# Execution Record 01

Date: 2026-10-19 (Asia/Karachi).

This record accompanies [Development Plan 01](development-plan-01.md). The
application remains a development build; source checks are not production certification.

## Implemented work

- Installable `src/cold_mailer/` Python package, Python 3.14.7 pin, uv lockfile,
  scoped package discovery, GUI/CLI entry points, dependency groups, Ruff, Pyrefly, strict
  pytest warnings/markers, coverage gates, and pre-commit configuration.
  The local pre-commit hook is installed in this checkout; new clones must install
  it using the README setup command.
- Application code is separated into domain, application, infrastructure, and UI
  packages, with CLI, settings, and bootstrap modules inside `cold_mailer`. Package
  imports replace all former top-level imports. The repository verifier rejects
  root Python scripts, obsolete imports, and domain dependencies on outer layers.
  Build tools, artifact manifests, coverage gates, and debugger launchers follow
  the package paths. The version wrapper remains removed.
- PySide6 Widgets workbench with real model/view tables, filtering/sorting, sender
  settings, OS credentials, campaign persistence, import diagnostics, exact-body
  review/edit/approval, explicit network control, cancellation, and worker lifecycle.
- Refreshed presentation with shared light/dark/system palettes, profile-persisted
  appearance, synchronized header/settings selectors, themed popup views and SVG
  indicators, consistent 40-pixel form controls, scrolling forms, action hierarchy,
  empty/filter states, and resizable recipient/editor cards. Brief/activity remains
  reachable in the fixed action bar on compact windows. Appearance changes preserve
  drafts, approvals, and the explicit network setting.
- Worker completion now retains thread references until a nonblocking zero-timeout
  join confirms native cleanup. An owned timer polls completion without freezing
  the UI. Theme callbacks use QObject slots and layout timers are window-owned.
  The new regression explicitly exercises delayed cleanup and close behavior.
- Shared service/domain/port boundaries, independent SQLite connections and short
  transactions, journalled attempts, approval hashes/revision guards, suppression,
  pacing/rolling daily budgets, bounded retry eligibility, process/profile ownership,
  uncertain-outcome recovery, and explicit reconciliation.
- Maintained Google GenAI adapter with explicit model, minimal personalization,
  one bounded provider attempt, structural/content validation, and redacted errors.
- SMTP envelope/MIME validation, explicit STARTTLS/implicit TLS, certificate
  verification, outcome classification, and cleanup independent of acceptance.
- Bounded CSV/XLSX import; unsupported XLS rejection; missing/duplicate header and
  row errors; restricted substitutions-only wrappers; no AI placeholders can send.
- Consistent database backup, conservative restore to a new profile, and explicit
  read-only legacy account import. Existing repository-local private files remain intact.
- CLI authoring/review/dry-run/send/reconcile/suppression/backup/restore commands.
- Pinned GitHub Actions workflows, CodeQL definition, dependency update definition,
  local actionlint/Gitleaks bootstrap with pinned checksums, and executable local
  Fast/Full/Security/Release gates. Release deliberately refuses to certify missing
  manual/hosted acceptance.

## Verification and known findings

All test inputs are synthetic. Real mail/AI providers were not contacted.

| Local verification | Result |
| --- | --- |
| `scripts/verify.ps1 -Mode Fast` | Passed lint, formatting, types, repository checks, and 34 unit tests. |
| `scripts/verify.ps1 -Mode Full` | Passed 99 offline tests, including Qt workflows, appearance persistence/interaction/resize checks, delayed thread cleanup, and real loopback TLS/SMTP. The runner explicitly includes all tool groups so prior runtime-only syncs cannot break type checks. |
| Application line/branch coverage | 94.26% combined; domain 100%, engine 100%, persistence 98.35%, SMTP 97.22%; theme 96.55%, shared UI components 96.40%. |
| Pyrefly | Zero errors and zero warnings after adding openpyxl stubs and correcting the contextmanager annotation. |
| Bandit | No findings in maintained application/helpers; installed test environments and generated artifacts are outside this static-analysis scope. |
| actionlint | All three workflow definitions pass local validation. Hosted execution remains open. |
| Current publishable-source Gitleaks scan | Zero findings; ignored local secrets are not copied into this snapshot. |
| Historical Gitleaks scan | Six redacted findings across five paths; history remediation remains open. |
| Locked runtime audit | Initial cryptography advisories fixed by upgrading to 50.0.2; final audit found no known vulnerabilities across 42 runtime dependencies. |
| Source/wheel boundaries | Package source and original SVG controls are explicitly included and checked for exact source equality in both archives. No root modules or private state enter the wheel, and no private state/caches enter the source archive. |
| Independent wheel installation | Reinstalled the refreshed wheel into a separate environment. Package/SVG resources and GUI/CLI entry points work outside the checkout. Both saved light/dark preferences are verified from rendered startup snapshots. Former flat imports remain absent. |
| Unsigned Windows executable | Rebuilt and launched outside the checkout with saved light/dark preferences: exit 0 in 4.81/2.68 seconds. Manifest hashes match 26 Python files, six SVG indicators, the lockfile, and executable; bundled SVG renderer and indicator bytes are verified. |
| Structural guard negative checks | Synthetic root script, obsolete top-level import, and domain-to-UI dependency each fail repository validation. Existing private data remains byte-for-byte unchanged. |
| Native visual checks | Every page inspected in light/dark appearance; synthetic captures generated at actual device ratios 1.0 and 2.0, including a 1000 x 650 compact window. Popup-arrow, spin-button, checkbox, theme persistence, and geometry behavior also have automated tests. |
| Negative checks | Deliberate synthetic lint/type/test/workflow/secret-fixture/stale-lock defects each produce a failing exit code. These are local probes, not hosted branch-rule verification. |

Local reports are ignored under `reports/`: JUnit, coverage, redacted scanner and
advisory results, wheel/executable smoke records, negative-check results, and UI
snapshots. Do not upload this whole directory: it also contains isolated testing
environments and temporary diagnostic state.

The executable is `dist/desktop/ColdMailer/ColdMailer.exe`, with `_internal` beside
it. Its development manifest records hashes and explicitly identifies unsigned,
uncommitted source. This is a development preview, not a signed installer or a
production-certified release. Native UI rendering was inspected. When Windows'
offscreen plugin cannot discover Segoe UI, the theme loader reads the installed
OS fonts for readable tests; these proprietary fonts are not bundled or copied.
`scripts/preview_ui.py` creates only temporary synthetic profiles and saves ignored
screenshots and size/scale metadata under `reports/ui-preview/`.

Thread cleanup follows Qt's distinction between the `finished()` signal and full
native completion; see the [QThread lifecycle documentation](https://doc.qt.io/qt-6/qthread.html).

- A real local TLS/SMTP fixture verifies trusted certificate delivery and rejection
  of an untrusted certificate. Other transport fault cases use injected collaborators.
- Python 3.14 exposes a specific upstream `google-genai` typing deprecation. Only
  that exact warning is filtered; other warnings remain failures. Remove the filter
  when upstream stops using `_UnionGenericAlias`.
- Fixed process invocation in source/build helpers uses resolved executables and
  argument arrays without a shell. Narrow Bandit B404/B603 annotations document
  those audited tool calls; B310 covers only fixed HTTPS downloads with pinned hashes.
- The initial dependency audit found advisories against cryptography 48.0.1. The
  lockfile now uses cryptography 50.0.2; the repeat runtime audit has no known findings.
- A redacted all-reachable-history Gitleaks scan reports six findings across five
  historical paths. Current-tree cleanup does not fix these historical exposures.
  Credential rotation and coordinated history rewrite/publication remain open.

## Plan 01 closure and handoff

Plan 01 is complete as the delivered foundation phase. All remaining execution
and acceptance gates have transferred to [Development Plan 02](development-plan-02.md),
including the original E00-E23 obligations, historical-secret remediation, hosted
checks, schema/recovery hardening, provider evidence, accessibility/performance,
and final installer/signing/release acceptance. None is marked implemented merely
because the foundation plan closed.

This record remains historical implementation evidence. Record later execution
against Plan 02; do not reinterpret this record as production certification.
