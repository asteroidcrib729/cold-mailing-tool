# Maintenance Record 01: Licensing and Verification Status

Updated: 2026-11-01 (Asia/Karachi).

This record updates current documentation without rewriting the historical
results in [Execution 04](execution-04.md). [Plan 02](development-plan-02.md)
and [Plan 03](development-plan-03.md) retain their remaining acceptance gates.

## Open-source licensing

- The original code and documentation are licensed under [Apache-2.0](../LICENSE).
- [NOTICE](../NOTICE) identifies Faraz Hussain, the original author, and the
  repository/source URL. Its attribution text does not add license restrictions.
- Project metadata declares the SPDX expression and license files. Source and
  wheel archive verification requires the license and NOTICE with matching bytes.
- Desktop builds copy LICENSE, NOTICE, and third-party guidance into the payload.
  EXE/MSIX packaging retains those files; the Windows verifier checks them.
- [Third-party licensing](../THIRD_PARTY_NOTICES.md) identifies separate Qt,
  dependency, runtime, tool, and service obligations. A complete version-specific
  bundled-component inventory and redistribution review remain release work.

The pending Plan 02 whitespace cleanup is included in this maintenance change.
No provider credentials or private runtime data are part of the licensing change.

The current audit also found four decoder denial-of-service advisories affecting
the previously locked pyasn1 0.6.4. This change pins the patched 0.6.5 release with
PyPI's published artifact hashes. The
[upstream release](https://github.com/pyasn1/pyasn1/releases/tag/v0.6.5) lists the
four fixes. Other dependency versions are unchanged; the patched runtime audit
reports no known vulnerabilities as of this verification pass.

## Previously verified account connection

On 2026-10-20, the owner's personal Google sign-in produced a connected sender,
an identity-bound OS-vault grant with Gmail sending permission and a refresh
token, and a matching verified identity from Google's read-only userinfo endpoint
(HTTP 200). No live email was sent. Credential values and personal email addresses
are intentionally omitted from this public record.

This is historical authentication evidence, not a current grant check or a send,
delivery, refresh-after-expiry, revocation, or packaged-browser acceptance result.
Microsoft registration and equivalent live verification remain open.

## Previously verified dependency and installer checkpoint

All seven original Dependabot PRs were merged on 2026-10-21. The final checkpoint
was `076b4f4e1c516cb9ada3f00fb5c9ff0aea7eb7ea`, including Pyrefly 1.4 compatibility
and the certifi 2026.10.19 security update. Its 290 offline tests, coverage gates,
development, security, and CodeQL workflows passed. These versions and results
describe that checkpoint; current audits must run again for later changes.

The [hosted Windows preview run](https://github.com/asteroidcrib729/cold-mailing-tool/actions/runs/39628692302)
built EXE/MSIX packages and passed package/source/checksum checks. The downloaded
installers' SHA-256 values matched the uploaded checksum list. EXE installation,
same-version reinstall, uninstall, and synthetic profile preservation passed on
the hosted Windows runner. The unsigned MSIX was inspected, not installed.

That checkpoint predates this license addition. A fresh licensing build must
include the new notices; the old artifacts must not be described as containing
them. Current runs are available from
[repository Actions](https://github.com/asteroidcrib729/cold-mailing-tool/actions).

## Remaining release and live-provider gates

- Exact owner-approved recipient/message seed tests for Google and Microsoft.
- Microsoft sign-in and both providers' expiry, refresh, revocation, wrong-account,
  and packaged callback/storage behavior.
- Signed MSIX installation, clean-user-machine testing, supported-version
  upgrade/rollback, distribution identity/signing, and provider publishing review.
- Complete third-party notices/source obligations and a bundled dependency inventory.
- Remaining quota, concurrency, fault/load, accessibility, and acceptance work in
  the active plans. Passing CI does not close those gates automatically.
