"""Google OAuth 2.0 for a desktop app, with tokens kept in the OS keychain.

How the flow works (the "installed app" / loopback flow):
  1. `connect` opens your browser at Google's consent page, asking for SCOPES.
  2. You sign in and approve; Google redirects to http://localhost:<port>/ where
     a tiny temporary server (started by the library) receives a one-time code.
  3. The code is exchanged for an ACCESS token (valid ~1 hour) and a REFRESH
     token (long-lived; 7 days while the app is in Google's "Testing" mode).
  4. We store both in the macOS Keychain. Later, expired access tokens are
     renewed silently with the refresh token. JARVIS never sees your password.
"""
import json
import logging
from pathlib import Path
from typing import Protocol

logger = logging.getLogger("jarvis.google")

# Stage 1: read-only. Later stages add scopes (Google asks you to approve again).
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

_KEYRING_SERVICE = "jarvis"
_KEYRING_USER = "google-oauth-token"


class GoogleNotConnected(Exception):
    """No usable token. The message tells the user what to run."""


class TokenStore(Protocol):
    def load(self) -> str | None: ...
    def save(self, token_json: str) -> None: ...
    def delete(self) -> None: ...


class KeychainTokenStore:
    """macOS Keychain (or the platform's equivalent) via the `keyring` package.

    Better than a file: the OS encrypts it and ties access to your login.
    """

    def load(self) -> str | None:
        import keyring
        from keyring.errors import KeyringError
        try:
            return keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
        except KeyringError as exc:  # e.g. Linux server without a secret service
            raise GoogleNotConnected(f"No usable system keychain to store the Google token: {exc}") from exc

    def save(self, token_json: str) -> None:
        import keyring
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, token_json)

    def delete(self) -> None:
        import keyring
        from keyring.errors import PasswordDeleteError
        try:
            keyring.delete_password(_KEYRING_SERVICE, _KEYRING_USER)
        except PasswordDeleteError:
            pass


class InMemoryTokenStore:
    def __init__(self, token_json: str | None = None) -> None:
        self.token_json = token_json

    def load(self) -> str | None:
        return self.token_json

    def save(self, token_json: str) -> None:
        self.token_json = token_json

    def delete(self) -> None:
        self.token_json = None


_NOT_CONNECTED = "Google isn't connected. In backend/, run: uv run python -m app.google connect"


def connect(client_file: str, store: TokenStore) -> None:
    """Interactive: opens the browser for consent, then stores the token."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not Path(client_file).exists():
        raise GoogleNotConnected(
            f"OAuth client file not found at {client_file}. Download it from Google Cloud "
            "Console (Clients -> Desktop app -> Download JSON); see README.")
    flow = InstalledAppFlow.from_client_secrets_file(client_file, SCOPES)
    # port=0: pick any free port for the temporary redirect server.
    # prompt="consent": always return a refresh token, even on re-connect.
    creds = flow.run_local_server(port=0, prompt="consent")
    store.save(creds.to_json())
    logger.info("google.connected", extra={"scopes": creds.scopes})


def load_credentials(store: TokenStore):
    """Stored token -> usable Credentials, refreshing if expired.

    Blocking (may make an HTTP call to Google): call from a worker thread.
    """
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    raw = store.load()
    if not raw:
        raise GoogleNotConnected(_NOT_CONNECTED)
    creds = Credentials.from_authorized_user_info(json.loads(raw), SCOPES)
    if creds.valid:
        return creds
    if not creds.refresh_token:
        raise GoogleNotConnected(_NOT_CONNECTED)
    try:
        creds.refresh(Request())
    except RefreshError as exc:
        # Typical cause: the 7-day refresh token limit of apps in "Testing" mode,
        # or access revoked in your Google account settings.
        raise GoogleNotConnected(
            "Google access expired or was revoked. In backend/, run: "
            "uv run python -m app.google connect") from exc
    store.save(creds.to_json())  # persist the renewed access token
    return creds
