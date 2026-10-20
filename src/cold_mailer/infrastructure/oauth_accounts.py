"""Explicit personal-account OAuth grants; no mailbox passwords or embedded web views."""

from __future__ import annotations

import json
from dataclasses import replace
from threading import Event
from typing import cast

import msal
from filelock import FileLock
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from cold_mailer.domain.models import Sender, ValidationError, address, identifier
from cold_mailer.domain.ports import CredentialStore
from cold_mailer.infrastructure.oauth_browser import authorize_in_browser
from cold_mailer.infrastructure.oauth_secrets import OAuthSecrets
from cold_mailer.infrastructure.storage import Store
from cold_mailer.settings import Settings

GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send"
GOOGLE_SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", GMAIL_SEND]
MICROSOFT_SCOPES = ["Mail.Send", "User.Read"]
CONSUMER_TENANT = "9188040d-6c67-4c5b-b112-36a304b66dad"
CONSUMER_AUTHORITY = "https://login.microsoftonline.com/consumers"
GOOGLE_OAUTH_EXCHANGE_URL = "https://oauth2.googleapis.com/token"


class OAuthAccounts:
    def __init__(self, settings: Settings, store: Store, credentials: CredentialStore) -> None:
        self.settings, self.store = settings, store
        self.secrets = OAuthSecrets(credentials)

    def _google_client(self) -> str:
        value = self.settings.google_oauth_client_id
        if not value or not value.endswith(".apps.googleusercontent.com"):
            raise ValidationError(
                "Google sign-in is not configured for this build. See the account setup guide."
            )
        return value

    def _microsoft_client(self) -> str:
        import uuid

        value = self.settings.microsoft_oauth_client_id
        try:
            uuid.UUID(value)
        except ValueError:
            raise ValidationError(
                "Microsoft sign-in is not configured for this build. See the account setup guide."
            ) from None
        return value

    def _request(self, *args, **kwargs):
        kwargs["timeout"] = self.settings.timeout
        return Request()(*args, **kwargs)

    def _google_identity(self, token: str) -> tuple[str, str]:
        claims = id_token.verify_oauth2_token(token, self._request, self._google_client())
        email = address(str(claims.get("email", ""))).lower()
        subject = claims.get("sub")
        if (
            claims.get("email_verified") is not True
            or claims.get("hd")
            or email.rsplit("@", 1)[1] not in {"gmail.com", "googlemail.com"}
            or not isinstance(subject, str)
            or not subject
        ):
            raise ValidationError("Only verified personal Gmail accounts can be connected.")
        return subject, email

    def _google_connect(self, stop: Event) -> dict:
        client_id = self._google_client()
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": client_id,
                    "client_secret": self.settings.google_oauth_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": GOOGLE_OAUTH_EXCHANGE_URL,
                }
            },
            scopes=GOOGLE_SCOPES,
            autogenerate_code_verifier=True,
        )

        def authorization(redirect: str, state: str) -> str:
            flow.redirect_uri = redirect
            return flow.authorization_url(
                state=state, access_type="offline", prompt="select_account consent"
            )[0]

        _, response = authorize_in_browser(authorization, stop)
        flow.fetch_token(code=response["code"], timeout=self.settings.timeout)
        credentials = cast(Credentials, flow.credentials)
        if (
            not credentials.id_token
            or not credentials.refresh_token
            or not credentials.has_scopes([GMAIL_SEND])
        ):
            raise ValidationError(
                "Google sending permission was not granted. Sign in and approve sending access."
            )
        subject, email = self._google_identity(credentials.id_token)
        return {
            "provider": "google",
            "subject": subject,
            "email": email,
            "client_id": client_id,
            "credentials": credentials.to_json(),
        }

    def _microsoft_app(self, cache: msal.SerializableTokenCache):
        return msal.PublicClientApplication(
            self._microsoft_client(),
            authority=CONSUMER_AUTHORITY,
            token_cache=cache,
            timeout=self.settings.timeout,
            enable_pii_log=False,
        )

    def _microsoft_connect(self, stop: Event) -> dict:
        import httpx

        cache = msal.SerializableTokenCache()
        app = self._microsoft_app(cache)
        flow = {}

        def authorization(redirect: str, state: str) -> str:
            flow.update(
                app.initiate_auth_code_flow(
                    MICROSOFT_SCOPES, redirect_uri=redirect, state=state, prompt="select_account"
                )
            )
            url = flow.get("auth_uri")
            if not isinstance(url, str):
                raise ValidationError(
                    "Microsoft could not start sign-in. Check the app registration."
                )
            return url

        _, response = authorize_in_browser(authorization, stop, loopback_host="localhost")
        result = app.acquire_token_by_auth_code_flow(flow, response)
        claims = result.get("id_token_claims", {})
        subject = claims.get("oid")
        scopes = str(result.get("scope", "")).casefold().split()
        if (
            not result.get("access_token")
            or claims.get("tid") != CONSUMER_TENANT
            or not isinstance(subject, str)
            or not subject
            or not {"mail.send", "https://graph.microsoft.com/mail.send"}.intersection(scopes)
        ):
            raise ValidationError(
                "Sign in with a personal Microsoft account. Work and school accounts are outside this application's scope."
            )
        with httpx.Client(timeout=self.settings.timeout, follow_redirects=False) as client:
            profile = client.get(
                "https://graph.microsoft.com/v1.0/me?$select=mail,userPrincipalName",
                headers={"Authorization": "Bearer " + result["access_token"]},
            )
            profile.raise_for_status()
            data = profile.json()
        email = address(data.get("mail") or data.get("userPrincipalName") or "").lower()
        accounts = app.get_accounts()
        if len(accounts) != 1 or not accounts[0].get("home_account_id"):
            raise ValidationError(
                "Microsoft did not identify one personal account. Start sign-in again."
            )
        return {
            "provider": "microsoft",
            "subject": subject,
            "email": email,
            "client_id": self._microsoft_client(),
            "account_id": accounts[0]["home_account_id"],
            "cache": cache.serialize(),
        }

    def connect(self, provider: str, stop: Event, sender_id: str | None = None) -> Sender:
        self.settings.require_network()
        if provider not in {"google", "microsoft"}:
            raise ValidationError("Choose Google Gmail or Microsoft Outlook sign-in.")
        try:
            session = (
                self._google_connect(stop)
                if provider == "google"
                else self._microsoft_connect(stop)
            )
            if stop.is_set():
                raise ValidationError("Sign-in was cancelled; no account was connected.")
            with FileLock(str(self.store.path) + ".send.lock", timeout=0):
                existing = (
                    self.store.sender(sender_id)
                    if sender_id
                    else next(
                        (
                            item
                            for item in self.store.senders()
                            if item.provider == provider and item.subject == session["subject"]
                        ),
                        None,
                    )
                )
                if existing and (
                    existing.email.casefold() != session["email"].casefold()
                    or (
                        existing.provider
                        and (
                            existing.provider != provider or existing.subject != session["subject"]
                        )
                    )
                ):
                    raise ValidationError(
                        "Sign in with the same account to reconnect this sender. Add a separate account for another identity."
                    )
                sender = Sender(
                    existing.id if existing else identifier(),
                    session["email"],
                    "gmail.googleapis.com" if provider == "google" else "graph.microsoft.com",
                    443,
                    session["email"],
                    "tls",
                    provider=provider,
                    subject=session["subject"],
                )
                if existing:
                    sender = replace(
                        sender, daily_limit=existing.daily_limit, interval=existing.interval
                    )
                sender.validate()
                self.secrets.save(sender.id, session)
                try:
                    self.store.save_sender(sender)
                    self.store.save_preference("oauth.connected." + sender.id, "true")
                except Exception:
                    self.secrets.delete(sender.id)
                    raise
                return sender
        except ValidationError:
            raise
        except Exception:
            raise ValidationError(
                "Account sign-in failed. Check the provider configuration and try again; no email was sent."
            ) from None

    def status(self, sender: Sender) -> str:
        if sender.provider not in {"google", "microsoft"}:
            return "Sign-in required. Legacy SMTP accounts cannot send."
        try:
            self._bound_session(sender)
            return "Signed in locally. Authorization is checked before sending."
        except ValidationError:
            return "Sign-in required. Reconnect this account before sending."

    def _bound_session(self, sender: Sender) -> dict:
        sender.validate()
        if not sender.provider:
            raise ValidationError(
                "Password-based SMTP sending is retired. Sign in with Google or Microsoft."
            )
        if self.store.preference("oauth.connected." + sender.id) != "true":
            raise ValidationError("This account is disconnected. Sign in again before sending.")
        session = self.secrets.load(sender.id)
        if any(
            session.get(name) != getattr(sender, name) for name in ("provider", "subject", "email")
        ):
            raise ValidationError(
                "Sender identity does not match its authorization. Sign in again."
            )
        return session

    def access_token(self, sender: Sender) -> str:
        self.settings.require_network()
        session = self._bound_session(sender)
        try:
            if sender.provider == "google":
                if session.get("client_id") != self._google_client():
                    raise ValidationError("Google app registration changed. Sign in again.")
                credentials = Credentials.from_authorized_user_info(
                    json.loads(session["credentials"])
                )
                if not credentials.has_scopes([GMAIL_SEND]):
                    raise ValidationError("Google sending permission is missing. Sign in again.")
                if not credentials.valid:
                    credentials.refresh(self._request)
                    session["credentials"] = credentials.to_json()
                    self.secrets.save(sender.id, session)
                token = credentials.token
            else:
                if session.get("client_id") != self._microsoft_client():
                    raise ValidationError("Microsoft app registration changed. Sign in again.")
                cache = msal.SerializableTokenCache()
                cache.deserialize(session["cache"])
                app = self._microsoft_app(cache)
                account = next(
                    (
                        item
                        for item in app.get_accounts()
                        if item.get("home_account_id") == session.get("account_id")
                    ),
                    None,
                )
                if account is None:
                    raise ValidationError(
                        "Microsoft account authorization is missing. Sign in again."
                    )
                result = app.acquire_token_silent_with_error(MICROSOFT_SCOPES, account=account)
                token = result.get("access_token") if result else None
                if cache.has_state_changed:
                    session["cache"] = cache.serialize()
                    self.secrets.save(sender.id, session)
            if not isinstance(token, str) or not token or len(token) > 64000:
                raise ValidationError(
                    "Authorization expired or was revoked. Sign in again before sending."
                )
            return token
        except ValidationError:
            raise
        except Exception:
            raise ValidationError(
                "Authorization could not be refreshed. Sign in again; no email was submitted."
            ) from None

    def disconnect(self, sender_id: str) -> None:
        try:
            with FileLock(str(self.store.path) + ".send.lock", timeout=0):
                self.store.hold_sender(sender_id)
                self.secrets.delete(sender_id)
        except ValidationError:
            raise
        except Exception:
            raise ValidationError(
                "Could not disconnect this account. Stop active operations and check OS credential storage."
            ) from None
