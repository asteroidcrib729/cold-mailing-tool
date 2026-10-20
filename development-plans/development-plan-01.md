# Development Plan 01: Foundation Complete

Date closed: 2026-10-19 (Asia/Karachi).

Status: **Complete**. This foundation phase is closed at the owner's request.
All unfinished implementation, security, verification, and release obligations
have moved to [Development Plan 02](development-plan-02.md). Closure does not
assert that those obligations were implemented or that the application is
production-certified.

The canonical filename is now `development-plans/development-plan-01.md`, using
the singular spelling requested for this handoff. It replaces the earlier
`development-plans-01.md`; there is no second active copy.

## Delivered foundation

- [x] Remove obsolete version/archive clutter and the version-directory wrapper;
  preserve the local environment file, contact data, database, and encryption key.
- [x] Organize the installable application into `src/cold_mailer/` with domain,
  application, infrastructure, and UI packages; retain dedicated support folders.
- [x] Establish uv metadata/lockfile, entry points, dependency groups, linting,
  type checks, strict offline tests, coverage gates, and local commit hooks.
- [x] Implement shared GUI/CLI campaign services, individual recipient drafts,
  SQLite persistence, OS credential access, explicit model/network choices,
  secure SMTP modes, approval checks, suppression, pacing, and recovery holds.
- [x] Build the PySide6 campaign/editor, sender, and settings screens with saved
  light/dark/system appearance, consistent controls, and safe worker lifecycle.
- [x] Add local security/workflow/artifact checks and GitHub quality/security
  workflow definitions; produce a locally tested wheel and unsigned directory preview.
- [x] Record actual evidence and limitations in [Execution Record 01](execution-01.md).
- [x] Transfer all 199 previously unchecked obligations, their original acceptance
  context, F01-F13/N01-N05 contracts, E00-E23 runbook, and open execution gates to
  Plan 02 without converting them into false completion claims.

## Evidence at closure

The last implementation record reports 99 passing offline tests, 94.26% combined
coverage, passing local lint/type/security/workflow/current-source checks, and
wheel/executable startup verification outside the checkout in both light and dark
appearance. These are recorded baseline results, not a fresh test run performed
by this documentation handoff.

Current source is distinct from Git history: six historical secret findings,
credential rotation, remote history remediation, hosted required checks, real
provider acceptance, installer/signing work, and clean-machine release acceptance
remain assigned to Plan 02. An unsigned application directory is not an EXE
installer or an MSIX release.

## Transfer and document navigation

| Document | Role |
| --- | --- |
| [Development Plan 02](development-plan-02.md) | Active feature requirements, execution order, decisions, complete inherited specification, and all unfinished obligations. |
| [Execution Record 01](execution-01.md) | Historical implementation and local verification evidence for this phase. |
| [Features and Improvements](features-and-improvements.md) | Separate candidate backlog for the owner's next scope discussion. |
| [Project README](../README.md) | Current application setup and operation. |

Plan 02 contains the original specification and a section-by-section transfer
inventory. The handoff preserved all 199 unchecked items and all surrounding
prose/tables rather than deleting acceptance details or marking them done.
The original document SHA-256 is recorded there for traceability.

No further implementation work is assigned to Plan 01. Add future requirements to
Plan 02 and record execution there; keep this closure and its evidence historical.

## Change boundary for this handoff

This change updates documentation and navigation. Application code, SQLite schema,
workflow YAML, local credential/data files, and existing Git staging are preserved.
No commit, push, live send, history rewrite, signing, or release publication is
performed by this handoff.
