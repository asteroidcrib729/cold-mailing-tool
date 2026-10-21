"""Versioned OS-vault chunks: token caches never enter SQLite or plaintext files."""

from __future__ import annotations

import contextlib
import json
import re
import uuid

from cold_mailer.domain.models import ValidationError
from cold_mailer.domain.ports import CredentialStore


class OAuthSecrets:
    def __init__(self, credentials: CredentialStore) -> None:
        self.credentials = credentials

    def _manifest(self, sender_id: str) -> tuple[str, int] | None:
        value = self.credentials.get("oauth:" + sender_id)
        if value is None:
            return None
        try:
            item = json.loads(value)
            generation, count = item["generation"], item["count"]
            if not isinstance(generation, str) or not re.fullmatch(r"[0-9a-f]{32}", generation):
                raise ValueError
            if type(count) is not int or not 1 <= count <= 256:
                raise ValueError
            return generation, count
        except ValueError, KeyError, TypeError:
            raise ValidationError(
                "Stored authorization is damaged. Disconnect and sign in again."
            ) from None

    @staticmethod
    def _key(sender_id: str, generation: str, index: int) -> str:
        return f"oauth:{sender_id}:{generation}:{index}"

    def load(self, sender_id: str) -> dict:
        manifest = self._manifest(sender_id)
        if manifest is None:
            raise ValidationError(
                "Sign in with your personal Google or Microsoft account before sending."
            )
        generation, count = manifest
        chunks = [self.credentials.get(self._key(sender_id, generation, i)) for i in range(count)]
        try:
            if any(not isinstance(chunk, str) or len(chunk) > 1000 for chunk in chunks):
                raise ValueError
            value = json.loads("".join(chunk for chunk in chunks if chunk is not None))
            if not isinstance(value, dict):
                raise ValueError
            return value
        except TypeError, ValueError:
            raise ValidationError(
                "Stored authorization is incomplete. Disconnect and sign in again."
            ) from None

    def save(self, sender_id: str, value: dict) -> None:
        serialized = json.dumps(value, ensure_ascii=True)
        if not 1 <= len(serialized) <= 256000:
            raise ValidationError("Provider authorization exceeds the secure storage limit.")
        previous = self._manifest(sender_id)
        generation = uuid.uuid4().hex
        chunks = [serialized[i : i + 1000] for i in range(0, len(serialized), 1000)]
        try:
            for i, chunk in enumerate(chunks):
                self.credentials.set(self._key(sender_id, generation, i), chunk)
            # Publish last; interrupted writes cannot replace a complete earlier cache.
            self.credentials.set(
                "oauth:" + sender_id, json.dumps({"generation": generation, "count": len(chunks)})
            )
        except ValidationError:
            self._remove_chunks(sender_id, generation, len(chunks))
            raise
        if previous:
            self._remove_chunks(sender_id, *previous)

    def _remove_chunks(self, sender_id: str, generation: str, count: int) -> None:
        for i in range(count):
            with contextlib.suppress(ValidationError):
                self.credentials.delete(self._key(sender_id, generation, i))

    def delete(self, sender_id: str) -> None:
        try:
            manifest = self._manifest(sender_id)
        except ValidationError:
            manifest = None
        self.credentials.delete("oauth:" + sender_id)
        if manifest:
            self._remove_chunks(sender_id, *manifest)
