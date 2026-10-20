# Features and Improvements: Candidate Backlog

Date: 2026-10-19 (Asia/Karachi).

Status: proposals for owner consideration, not approved implementation scope.
The owner can add, reject, combine, or reprioritize ideas while
[Development Plan 02](development-plan-02.md) is being refined.

The requested smooth scrolling, durable SQLite history, individualized messages,
additive pacing jitter, autosave toggles, concurrency, and EXE/MSIX workflows are
already requirements in Plan 02. They are deliberately not counted as new ideas here.
Some proposals extend older general acceptance requirements; promotion must point
to the existing requirement instead of creating conflicting duplicate tasks.

## How to choose and promote an idea

Priority describes suggested value, not a delivery promise. Effort is relative:
S is localized, M crosses a subsystem, and L involves integration or several
subsystems. Validate effort after design. Every proposal remains unchecked until
the owner decides whether it belongs in the active plan.

For promotion, add a Plan 02 requirement ID, concrete user story, dependency,
privacy/security impact, data migration impact, owner, acceptance test, and
execution step. Link the decision back here. Do not build speculative integrations
or contact external services simply because an idea appears in this file.

## Priority 1: Make the product easier to understand and use

### FI-01: Built-in demonstration workspace

- [ ] Offer a clearly marked demo profile with synthetic contacts and fake AI/SMTP
  adapters, useful for learning, screenshots, and portfolio demonstrations.
- Acceptance: a new user can complete a campaign journey without an account,
  credentials, network, or any possibility of transmitting demo messages. Leaving
  the demo returns to the chosen real profile without copying demo credentials.
- Effort: M. Dependency: profile/job boundaries. Main risk: confusing demonstration
  success with provider delivery; keep the banner and fake outcomes explicit.

### FI-02: Import mapping with reusable source profiles

- [ ] Preview an import, map unfamiliar headers to supported fields, save mappings
  for common source formats, and show sample values before committing rows.
- Acceptance: import `Email Address`, `Given Name`, and custom columns without
  manually editing the source file; duplicate/invalid mappings have actionable
  diagnostics and the original file is unchanged.
- Effort: M. Dependency: existing bounded importer. Main risk: silent wrong-column
  assignment; require a visible preview and explicit confirmation.

### FI-03: Versioned campaign blueprints

- [ ] Save reusable campaign setup recipes containing an approved factual offer,
  brief structure, variable schema, and workflow defaults.
- Acceptance: create a new campaign from a named blueprint version without changing
  earlier campaigns or automatically approving their generated messages.
- Effort: M. Dependency: campaign settings. Main risk: carrying stale facts forward;
  show version/change notes and require review for each campaign.

### FI-04: Saved views and contact segments

- [ ] Save frequently used filters and named segments based on tags or contact
  attributes, with a preview of the selected recipients.
- Acceptance: reopen a saved view after restart, explain the matching rules, and
  freeze a run's selected IDs so later segment edits cannot expand an active send.
- Effort: M. Dependency: stable contact IDs and query service. Main risk: accidental
  audience expansion; distinguish live views from frozen run selections.

### FI-05: Command palette and keyboard help

- [ ] Add searchable commands for navigation, recipient lookup, view changes, and
  safe authoring actions, plus a visible keyboard shortcut reference.
- Acceptance: perform the main authoring/review journey without a mouse; live
  transmission still requires its existing explicit confirmation.
- Effort: S/M. Dependency: centralized actions. Main risk: hidden shortcuts causing
  unexpected state changes; expose shortcuts and preserve focus/accessibility.

### FI-06: Mail-client reading previews

- [ ] Preview plain-text subject/body wrapping at narrow and wide reading widths,
  show subject truncation examples, and flag unusually long unbroken text.
- Acceptance: inspect the same saved revision at two widths without modifying it;
  explain that these are approximations, not exact rendering by every mail client.
- Effort: S. Dependency: immutable revision preview. Main risk: false fidelity
  claims; keep the preview simple and avoid introducing HTML sending implicitly.

### FI-07: Explainable content-quality review

- [ ] Flag unsupported claims, overly vague personalization, missing factual input,
  and excessive length; show the contact fact or supplied brief behind a suggestion.
- Acceptance: the user can dismiss a suggestion, see its rationale, and retain
  manual wording. Suggestions never invent facts or approve content automatically.
- Effort: M/L. Dependency: generation provenance and evaluation fixtures. Main risk:
  presenting model opinions as facts; distinguish deterministic rules from AI advice.

### FI-08: Guided first-run checklist

- [ ] Offer short, resumable setup guidance with clear prerequisites and links to
  the relevant screen, followed by a synthetic rehearsal before a live seed test.
- Acceptance: missing model, sender, credential, contact, or approval state has a
  specific next action; the guide can be dismissed and reopened.
- Effort: S/M. Dependency: application diagnostics. Main risk: implying a green
  setup check guarantees delivery; explain exactly what each check establishes.

## Priority 2: Improve campaign organization and follow-through

### FI-09: Quiet hours and recipient-timezone windows

- [ ] Add visible, configurable local-time sending windows with timezone source
  and confidence, daylight-saving handling, and holiday exclusions if supplied.
- Acceptance: a run preview explains when each recipient becomes eligible, including
  ambiguous/missing timezone data; sleep/resume never creates a catch-up burst.
- Effort: M/L. Dependency: Plan 02 pacing scheduler. Main risk: guessing timezones
  from addresses; require user-provided or explicitly reviewed data.

### FI-10: Opt-in reply triage

- [ ] Explore read-only inbox integration to associate replies with outbound
  Message-IDs and present threads without turning the app into a full mail client.
- Acceptance: a reviewed test account demonstrates minimal access, explicit sync,
  disconnect/revocation, and a manual fallback. No external inbox is accessed by default.
- Effort: L. Dependency: provider/auth design and reply-matching tests. Main risks:
  overbroad mailbox permissions and storing unrelated messages.

### FI-11: Variable dictionary and insertion picker

- [ ] Provide a searchable list of available template variables, sample values,
  required/optional status, and a safe insertion action at the cursor.
- Acceptance: see which contacts lack a required field before generation; inserting
  a variable does not broaden the existing restricted template language.
- Effort: S/M. Dependency: importer schema and template validation. Main risk:
  confusing arbitrary code with substitutions; keep the supported grammar explicit.

### FI-12: Contact merge review

- [ ] Detect probable duplicate contact records and offer a field-by-field merge
  preview rather than silently replacing existing details.
- Acceptance: the user chooses surviving values, historical send identities stay
  unchanged, suppression is retained, and an unsent merge can be reversed.
- Effort: M. Dependency: stable contacts and history snapshots. Main risk: merging
  different people; require explicit review and retain provenance.

### FI-13: Contact-source and permission records

- [ ] Let operators record where a contact came from, when it was collected, its
  intended purpose, and any operator-reviewed contact restrictions.
- Acceptance: view/export provenance and filter records needing review. This is
  recordkeeping, not an automated determination of legal permission or compliance.
- Effort: M. Dependency: contact metadata and retention policy. Main risk: implying
  that filling in a field establishes permission; keep operator responsibility clear.

### FI-14: Separated brand/client workspaces

- [ ] Explore separate workspaces for different brands or clients, with explicit
  sender, template, credential, export, and data boundaries.
- Acceptance: a cross-workspace isolation test proves that credentials and content
  cannot be mixed accidentally. Decide suppression inheritance before enabling sends.
- Effort: L. Dependency: profile/coordinator design and credential namespace review.
  Main risk: weakening isolation by sharing writable state indiscriminately.

### FI-15: Reusable local workflow actions

- [ ] Let the user save a small sequence of safe local actions, such as apply tag,
  open review view, validate a selection, and prepare an export.
- Acceptance: preview the steps, invoke them explicitly, and see partial failure
  results. Sending and external service actions remain outside the initial macro scope.
- Effort: M. Dependency: typed application commands. Main risk: hidden automation;
  avoid arbitrary scripts and keep each side effect visible.

### FI-16: Honest campaign reports

- [ ] Create user-selected reports for processing outcomes, reply/feedback counts
  when actually available, and common failure reasons, with clear date/time scope.
- Acceptance: exported totals reconcile to durable records. SMTP acceptance,
  provider delivery feedback, and replies are separate metrics with missing-data labels.
- Effort: M. Dependency: Plan 02 history and optional feedback integration. Main
  risk: misleading success rates or exposing recipients in broadly shared reports.

## Priority 3: Strengthen portability, diagnostics, and long-term use

### FI-17: Encrypted portable backup packages

- [ ] Explore opt-in encrypted backup/export with explicit recovery-key ownership,
  verification before replacement, and a documented restore rehearsal.
- Acceptance: a second clean test profile restores the intended data with the
  correct recovery secret and fails safely with the wrong one. Passwords remain
  excluded unless a separately reviewed secure credential export is approved.
- Effort: L. Dependency: existing backup API, cryptographic format/version design,
  and key recovery policy. Main risk: unrecoverable backups or false protection claims.

### FI-18: Previewable support bundles

- [ ] Build a local diagnostic bundle containing selected version, job, native
  runtime, and redacted failure information, with a file-by-file preview.
- Acceptance: synthetic secrets/contact text are excluded by tests; the user can
  inspect/delete the bundle. Creation does not upload or send it anywhere.
- Effort: M. Dependency: structured diagnostics. Main risk: accidental data disclosure;
  prefer an allowlist and make inclusion of any sensitive material an explicit action.

### FI-19: Optional signed-update checks

- [ ] After release signing is established, explore an opt-in update checker with
  verified metadata, channel/version information, and a manual installation handoff.
- Acceptance: reject altered metadata/download hashes, incompatible schemas,
  wrong channels, and unauthorized downgrades; checking never starts a campaign.
- Effort: L. Dependency: signed release identity and tested upgrade/rollback policy.
  Main risk: supply-chain compromise or installing an incompatible database reader.

### FI-20: Font scale, density, and high-contrast controls

- [ ] Add readable font scaling, comfortable/compact density, and a high-contrast
  presentation option beyond the existing light/dark preference.
- Acceptance: keyboard focus and status meaning remain visible at enlarged fonts,
  high DPI, and color-vision variations, with no clipped buttons or fields.
- Effort: M. Dependency: shared UI components and assistive-technology review.
  Main risk: fixed geometry undermining accessibility; measure before declaring support.

### FI-21: Guided configuration repair

- [ ] Explain a missing credential, moved profile, incompatible schema, or unwritable
  data path with specific, reversible repair choices rather than a generic failure.
- Acceptance: a fixture for each failure demonstrates a safe next step, preserves
  the source data, and never silently generates/replaces a legacy encryption key.
- Effort: M. Dependency: typed diagnostics and migration/recovery contracts. Main
  risk: a repair action changing user state without a concrete preview.

### FI-22: Generation budget preview

- [ ] Estimate request count and optional user-supplied model cost assumptions
  before a generation batch, with a configurable request/spend ceiling.
- Acceptance: clearly label estimates and unknown pricing; stop new requests at
  the selected budget and retain completed drafts. Do not embed stale price claims.
- Effort: M. Dependency: provider usage metadata, job reservations, and selected
  model policy. Main risk: presenting an estimate as a billing guarantee.

### FI-23: Reviewed attachment support

- [ ] Consider explicit per-message attachments only after plain-text sending is
  reliable, including size/type rules, visible file lists, and snapshot hashes.
- Acceptance: no automatic directory attachment, changed/missing files invalidate
  approval, MIME content is tested, and exports/backups have an explicit file policy.
- Effort: L. Dependency: storage/privacy decisions, provider limits, and revised
  approval/content contracts. Main risk: sending the wrong file or private material.

### FI-24: Read-only developer environment doctor

- [ ] Add a deterministic command that diagnoses interpreter/uv/native SQLite/Qt
  versions, lock compatibility, scanner availability, and packaging prerequisites.
- Acceptance: a clean contributor environment receives actionable setup output
  without reading real credentials, installing tools silently, or modifying trust.
- Effort: S/M. Dependency: existing verifier and packaging scripts. Main risk:
  confusing diagnostics with certification; show observed versions and explicit gaps.

## Suggested shortlist for the next scope discussion

Start by considering FI-01 (demo workspace), FI-02 (import mapping), FI-05 (command
palette), FI-08 (guided setup), and FI-11 (variable picker). They make the existing
workflow easier to understand without requiring mailbox integration or a new
distribution service. This is a proposed discussion order, not authorization to
implement them before the owner finishes the feature list.

## Decision log template

| Proposal | Owner decision | Reason | Plan requirement / acceptance | Status |
| --- | --- | --- | --- | --- |
| FI-01 through FI-24 | Awaiting review | Owner is considering further features. | Promote individually when selected. | Proposed |

Keep future ideas in this file until selected. Record rejected/deferred ideas with
their rationale so they are not repeatedly reintroduced as unfinished obligations.
