# Execution 04: Personal Google and Microsoft OAuth Accounts

Date: 2026-10-20 (Asia/Karachi).

This implements the owner's [personal-account scope decision](development-plan-03.md).
Only explicit Google Gmail and personal Microsoft sign-in can authorize the normal
application's send path. Real consent and mailbox sending require the owner's
[publisher configuration](personal-account-setup.md) and later bounded live acceptance.

## Implemented changes

- Official Google OAuth and Microsoft MSAL integrations use system-browser code
  flow, SDK PKCE, unpredictable state, a three-minute callback window, and a
  loopback-only HTTP listener. Stop/cancel closes the listener; no mailbox password
  is requested. Callback checks cover host, path, duplicate parameters, state,
  provider destinations, malformed callbacks, and declined consent.
- Google ID tokens are verified with the official library against the configured
  client. Only verified personal Gmail identities without a hosted-domain claim
  are accepted. Microsoft uses only the consumer authority, checks the personal
  tenant and sending scope, and resolves the primary mailbox through Graph.
- Sender/provider/subject identity is bound to the OS-stored authorization. A
  reconnect cannot change an existing account's identity. Profile-scoped token
  caches use bounded Windows-vault chunks and a manifest published after all
  chunks; no plaintext file/SQLite fallback exists.
- Desktop sender settings provide Google/Microsoft sign-in, read-only email,
  local connection status, independent pacing/limit controls, and disconnect.
  Native Qt slots avoid keeping old windows alive through sign-in button closures.
  CLI uses `connect-account` and `disconnect-account`; `add-sender` is retired.
- Production bootstrap and GUI sending use only Gmail API/Graph OAuth transport.
  Legacy password metadata cannot authorize sending; it is rejected before a mail
  attempt is claimed. Old SMTP implementation/import readers remain internal
  compatibility code with offline fixtures, and have no production entry point.
- Token refresh happens after any pacing wait and before attempt admission, so a
  long wait does not deliberately age the selected bearer token. Revoked or missing
  authorization requires explicit sign-in; it cannot select a different account.
- Reviewed MIME, recipient/from binding, Message-ID, UTC date, durable attempt
  snapshots, suppression, frozen audience, approvals, jitter, pacing, and uncertain
  recovery remain in the shared engine. HTTP 401/403 stops for authorization;
  throttling stops and persists `Retry-After` (or a conservative fallback); a 5xx or
  interrupted POST is uncertain and cannot be automatically resubmitted.
- Schema v4 adds nonsecret provider/subject metadata and clears older pending
  approvals after a pre-upgrade backup. Existing accepted/uncertain history stays
  unchanged. Disconnect clears local grants and pending approvals without deleting
  history; provider consent revocation remains a separate account-settings action.
  The disconnected flag and approval invalidation are committed before deleting
  vault entries, so even a credential-deletion failure blocks the existing grant.

## Verification

The final full verifier passed **290 offline tests**, with **93.06% combined branch
coverage**. Domain models, OAuth account management, API transport, and OS-cache
storage are at 100%; browser callbacks are at 95.96%, campaign orchestration at
96.93%, and storage at 98.36%. All four OAuth modules were added to the existing
95% critical-module gate; the 90% aggregate threshold was retained. Ruff, formatting,
Pyrefly, repository/document links, actionlint, and the publishable-source Gitleaks
scan pass. Bandit reports zero findings with no additional suppressions, and the
updated locked runtime dependency audit reports zero known package vulnerabilities.
This does not close the existing native SQLite/WAL runtime prerequisite.

A synthetic **13,213-character** cache round trip passed against the actual Windows
OS credential store, and its manifest was removed afterward. This verifies the
chunking path without using real account tokens. Mock security/integration tests
cover grant binding, malformed/partial caches, failed cache publication, refresh,
disconnect failures, rejected organizations, rate-limit delay persistence, and
preservation of reviewed MIME. Real loopback HTTP tests cover Host/state validation
and callback logging boundaries.

An intermediate full run exposed native Qt timeout/access-violation behavior during
theme switching; the introduced self-capturing sign-in callbacks were replaced with
Qt slots. Seventeen targeted appearance/journey tests and the final full suite pass
after the correction. Intermediate failed runs are not counted as completed acceptance.

No real provider consent, account/password entry, Gemini generation request, or
mailbox send occurred in this implementation pass. The ignored `.env` and private
legacy runtime files were not edited or used as fixtures.

A fresh PyInstaller standalone desktop build completed and launched successfully
with an isolated smoke profile, saved a snapshot, and exited without provider calls.
The development manifest records exact source/lock/executable hashes and correctly
labels the build as an unsigned preview from a tree with pending documentation.
The existing optional `pycparser.lextab` / `yacctab` warnings remain; they did not
prevent import, launch, or snapshot capture. Real browser consent in the frozen
artifact remains unverified. EXE/MSIX installer artifacts were not rebuilt in this
pass and do not establish OAuth release acceptance.

Native source previews captured all five tabs in light/dark/contrast modes at
1000-by-650 logical pixels. The sender screen was visually inspected for aligned
fields, provider sign-in buttons, readable connection state, and scroll access.
These captures do not certify assistive-technology or live provider behavior.

## Owner-dependent and release work

1. Configure publisher-owned Google Desktop OAuth and personal-only Microsoft
   native app registrations using the exact guide, then perform real browser consent.
2. Verify both account types, rejected organization accounts, expiry/refresh,
   revocation, disconnect/reconnect, cancellation, and grant changes against providers.
3. Authorize one exact reviewed message to an owned recipient for each provider;
   compare API acceptance, actual receipt, local history, and repeat-run protection.
4. Package fresh installers with reviewed publisher configuration and verify native
   OAuth dependencies, browser callbacks/firewall behavior, credential persistence,
   standard-user install, upgrades, signing, and distribution requirements.
5. Continue Plan 02's remaining AI quota governance, broader quality/load/fault
   acceptance, and other unfinished release work. OAuth functional tests do not
   establish deliverability, bulk-use suitability, or provider policy approval.
