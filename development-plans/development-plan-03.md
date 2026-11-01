# Development Plan 03: Personal Mailbox Sign-In

Date: 2026-10-20 (Asia/Karachi).

The owner's latest scope decision overrides earlier SMTP/company-account plans:
senders must explicitly sign in with a **personal Google Gmail account** or a
**personal Microsoft Outlook account**. Generic SMTP, account passwords, app
passwords, Google Workspace, Microsoft 365 organizational accounts, work/school
tenants, shared mailboxes, company-domain integrations, and arbitrary From aliases
are outside the supported sending scope.

This is an account-authorization addendum to [Plan 02](development-plan-02.md),
not a claim that its other release and reliability obligations are complete.
[Execution 04](execution-04.md) records implementation and verification;
[publisher setup](personal-account-setup.md) records the remaining owner actions.

## Required account flow

1. The application remains usable for local authoring without network access.
2. The user chooses **Sign in with Google** or **Sign in with Microsoft** and
   explicitly enables Live access for that network operation.
3. The system browser handles account selection, authentication/MFA, and consent.
   The application has no mailbox-password entry or embedded login browser.
4. Authorization code flow uses SDK-managed PKCE and a validated unpredictable
   state, with a short-lived loopback listener and cooperative cancellation.
5. Verify provider identity and personal-account eligibility before persisting a
   connection. Reject insufficient consent, account substitution, wrong state,
   organizational accounts, malformed grants, and cancelled/timed-out sign-in.
6. Bind the sender email/provider/subject to the authorized account. Reconnecting
   an existing sender must retain that identity. A different account gets its own
   sender record and independent pacing/history.
7. Store reusable credentials only in the OS credential store, with no plaintext
   fallback. SQLite, logs, backups, support bundles, source, and CI artifacts must
   not contain tokens. Large caches must respect Windows credential-size limits.
8. Before each send admission, obtain a valid token for that exact sender. Refresh
   only an existing explicit grant; a missing/revoked grant requires user sign-in.
   Authentication failure cannot fall back to saved passwords or another account.
9. Submit reviewed MIME through Gmail API or Microsoft Graph. Preserve the shared
   revision/approval, frozen audience, journal, suppression, cancellation, daily
   budget, pacing, and uncertain-outcome contracts.
10. Disconnect removes local reusable authorization and invalidates pending
    approvals. Provider-side consent removal remains available in provider settings.
    Historical and uncertain outcomes remain immutable.

## Permissions and boundaries

| Provider | Account restriction | Requested access | Send endpoint |
| --- | --- | --- | --- |
| Google | Verified `gmail.com` / `googlemail.com` identity, no hosted-domain claim | OpenID identity/email and `gmail.send`; no inbox-reading scope | Gmail API `users/me/messages/send` |
| Microsoft | `consumers` authority and personal consumer-tenant identity | Delegated `Mail.Send`, basic account profile `User.Read`, SDK identity/refresh scopes | Microsoft Graph `/me/sendMail` |

Google and Microsoft sign-in configuration is separate from the Gemini API key.
One explicit account connection can persist across restarts; each message does not
require another login while the user-authorized grant remains valid. Account
connection never automatically approves content or sends a message.

## Execution and acceptance

- [x] Add official Google OAuth and Microsoft MSAL dependencies and locked resolution.
- [x] Add personal identity validation and OS-backed, versioned token-cache storage.
- [x] Add cancellable browser callbacks with state, path, Host, and destination checks.
- [x] Replace sender password/host/port fields and legacy import with sign-in controls.
- [x] Add CLI sign-in/disconnect commands and remove password-based sender creation.
- [x] Route normal desktop and CLI sending exclusively through OAuth APIs.
- [x] Reject legacy password accounts before mail-attempt admission; preserve old data.
- [x] Upgrade schema with pre-migration backup, account metadata, and invalidation
  of old pending approvals. Retain immutable attempt/revision history.
- [x] Stop the operation after authorization failure, a provider throttle, or an
  ambiguous POST result. Persist a provider rate-limit delay before explicit retry.
- [x] Add offline grant, identity, callback, vault, refresh, transport, and GUI tests.
- [x] Configure the owner's personal Google registration and verify sign-in with a
  read-only identity check (2026-10-20; see [maintenance evidence](maintenance-01.md)).
- [ ] Configure and verify the publisher-owned personal Microsoft OAuth registration.
- [ ] Test real Google and Microsoft browser consent, cancellation, refresh after
  expiry, revocation, disconnect/reconnect, and wrong-account rejection.
- [ ] Authorize one exact reviewed message to an owned recipient for each provider;
  distinguish API acceptance from observed receipt and inbox placement.
- [ ] Build fresh EXE/MSIX artifacts and verify OAuth dependencies, system-browser
  callbacks/firewall behavior, OS token storage, and upgrades on clean Windows.
- [ ] Complete Google public-app verification and provider publishing requirements
  where applicable, and provide release-time publisher client configuration.

An offline mock suite establishes application behavior, not successful provider
registration, live mailbox permission, actual sending, deliverability, or release
readiness. Earlier app-password instructions are superseded by this scope.
