# Personal Account Sign-In: Publisher and Operator Setup

Date: 2026-10-20 (Asia/Karachi).

Only personal Gmail and personal Microsoft Outlook accounts are supported.
The owner has not yet configured the OAuth registrations described below in this
checkout. The existing Gemini API key cannot authorize mailbox access.

## Google publisher setup

1. Open the Google Cloud console for the publisher's chosen project. The existing
   AI project may be used if it is under the publisher's control; it still requires
   separate OAuth configuration.
2. Enable **Gmail API**. Configure Google Auth Platform branding, audience,
   support/contact details, and the consent screen for this desktop application.
3. For a development app with an external testing audience, add the intended
   personal Gmail account as a test user. Request only `openid`,
   `https://www.googleapis.com/auth/userinfo.email`, and
   `https://www.googleapis.com/auth/gmail.send`.
4. Create an OAuth client of type **Desktop app**. Obtain its client ID and desktop
   client configuration. Do not create a service account or reuse the Gemini key.
5. Put the desktop client's values in the local ignored `.env`:

   ```dotenv
   GOOGLE_OAUTH_CLIENT_ID=
   GOOGLE_OAUTH_CLIENT_SECRET=
   ```

6. The application uses a dynamic IPv4 loopback port with
   `http://127.0.0.1:<port>/oauth/callback`, SDK-generated S256 PKCE, and a state
   value unique to each operation. Google verifies the ID token signature,
   issuer, audience, and expiry through its official library. Application checks
   additionally require verified personal Gmail identity and no Workspace domain.
7. Before public distribution, complete Google's applicable OAuth verification and
   consent/publishing requirements. `gmail.send` is a sensitive scope. Testing
   authorization is not equivalent to public-app approval or permanent token life.

Desktop clients cannot protect an embedded client secret as a confidential server
would. This application still keeps developer configuration untracked and handles
the issued user tokens as credentials. See Google's
[desktop authorization guide](https://developers.google.com/identity/protocols/oauth2/native-app)
and [scope classification](https://developers.google.com/workspace/gmail/api/auth/scopes).

## Microsoft publisher setup

1. In Microsoft Entra app registrations, create the publisher's application with
   **Personal Microsoft accounts only** as the supported audience. Register it as
   a public native desktop client. Creating/managing the registration may require
   an Entra directory and appropriate publisher permissions even though end users
   are personal Microsoft account holders.
2. Under **Mobile and desktop applications**, register the exact redirect path
   `http://localhost/oauth/callback`. The application selects a random local port;
   Microsoft ignores the port when matching localhost redirect URIs, but the path
   must match. The listener itself binds only to IPv4 loopback, never a LAN address.
3. Configure delegated Microsoft Graph **Mail.Send** and **User.Read**. The latter
   identifies the actual signed-in mailbox; it is not an inbox-reading permission.
   MSAL adds the identity/refresh scopes needed by its authorization-code flow.
   Do not use application-wide `Mail.Send`, a daemon grant, or a client secret.
4. Set the local ignored configuration:

   ```dotenv
   MICROSOFT_OAUTH_CLIENT_ID=
   ```

5. The application uses `https://login.microsoftonline.com/consumers` and MSAL's
   PKCE authorization-code flow. It checks the returned personal consumer tenant,
   binds a stable account subject and primary email, and refuses organizational
   sign-ins even if a registration is accidentally configured more broadly.
6. Verify real consumer consent with the configured registration. Confirm the
   account has an Outlook mailbox and that the requested scopes are granted.

References: [supported account audiences](https://learn.microsoft.com/en-us/entra/identity-platform/v2-supported-account-types),
[desktop tokens with MSAL](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens),
[localhost redirect matching](https://learn.microsoft.com/en-us/entra/identity-platform/reply-url),
and [Graph sendMail](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0).

## Connect and use an account

1. Launch from the source workspace with:

   ```powershell
   uv --cache-dir .uv-cache run --locked cold-mailer-desktop --development
   ```

   Outside explicit development mode, the root `.env` is not loaded. Publisher
   configuration can also be supplied in the process environment. A distributable
   build still needs a reviewed way to supply its publisher-owned registrations;
   previews without that configuration cannot complete browser sign-in.
2. Enable **Live access**, open **Sender accounts**, and choose **Sign in with Google**
   or **Sign in with Microsoft**. The system browser handles account selection,
   password entry, MFA, and consent. The desktop never asks for the mailbox password.
3. For another mailbox, choose **Add another** first. With an existing sender
   selected, sign-in is a reconnect and must match that same account. Legacy SMTP
   records can only be reconnected when the personal provider identity matches;
   unsupported company records remain readable historical data.
4. Check the displayed signed-in email. Set sending limits, author the recipient's
   exact subject/body, save and approve the revision. Account connection alone
   cannot send. **Send approved** separately requires Live access and confirmation.
5. **Disconnect** removes local token-cache references and clears pending approvals.
   It does not log out the browser or revoke the provider's server-side consent.
   A persisted disconnected flag blocks the old local grant even if OS cache deletion fails.
   Remove application access in Google/Microsoft account settings to revoke that
   grant as well. Deleting an account with campaign history is deliberately refused.

CLI equivalents use the same engine and OS credential namespace:

```powershell
uv --cache-dir .uv-cache run --locked cold-mailer --development --live connect-account google
uv --cache-dir .uv-cache run --locked cold-mailer --development --live connect-account microsoft
uv --cache-dir .uv-cache run --locked cold-mailer --development --live connect-account google --sender SENDER_ID
uv --cache-dir .uv-cache run --locked cold-mailer disconnect-account SENDER_ID
```

Provider passwords, authorization codes, API keys, and tokens must not be pasted
into chat, committed files, screenshots, support bundles, or CI logs. User refresh
tokens are stored as bounded versioned chunks in the OS credential store, with the
manifest published last. A missing or damaged cache blocks sending and requires
explicit reconnection. OS vault deletion failures can leave protected orphan chunks;
provider-side revocation remains the definitive way to invalidate a lost grant.

## Migration and live acceptance

Schema v4 backs up a recognized older profile before adding provider/subject
metadata. Legacy sender rows receive empty metadata; they cannot pass OAuth
preflight using old passwords. Approved/retryable old messages are returned to
unapproved drafts. Accepted/uncertain messages and historical snapshots are retained.
No credential, old runtime database, or encryption key is automatically imported.

The owner must perform real browser authentication. Testing configuration, error
handling, and mock API responses cannot prove provider approval. After sign-in,
agree on one owned recipient and one reviewed message per provider before sending.
No mailbox sends have been authorized or performed by this implementation pass.
