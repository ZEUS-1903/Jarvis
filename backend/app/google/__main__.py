"""Manage the Google connection.

    uv run python -m app.google connect      # opens your browser to approve access
    uv run python -m app.google status       # is JARVIS connected? which permissions?
    uv run python -m app.google disconnect   # delete the stored token from the Keychain

To fully revoke access, also remove "Jarvis" at
https://myaccount.google.com/connections
"""
import json
import sys

from app.config import get_settings
from app.google.auth import GoogleNotConnected, KeychainTokenStore, connect, load_credentials


def main(args: list[str]) -> None:
    store = KeychainTokenStore()
    command = args[0] if args else ""
    if command == "connect":
        connect(get_settings().google_client_file, store)
        print("Connected. JARVIS can now read your Gmail and Google Calendar.")
    elif command == "status":
        try:
            creds = load_credentials(store)
        except GoogleNotConnected as exc:
            print(f"Not connected: {exc}")
            return
        print("Connected. Permissions:")
        for scope in json.loads(store.load() or "{}").get("scopes", creds.scopes or []):
            print("  -", scope.rsplit("/", 1)[-1])
    elif command == "disconnect":
        store.delete()
        print("Token deleted from the Keychain. Also revoke at https://myaccount.google.com/connections")
    else:
        sys.exit(__doc__)


main(sys.argv[1:])
