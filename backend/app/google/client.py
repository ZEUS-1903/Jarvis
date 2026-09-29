"""Builds authenticated Gmail/Calendar API clients on demand."""
import threading

from app.google.auth import TokenStore, load_credentials


class GoogleClients:
    def __init__(self, store: TokenStore) -> None:
        self._store = store
        self._lock = threading.Lock()

    def service(self, api: str, version: str):
        """Blocking: may refresh the token over HTTP. Call from a worker thread."""
        from googleapiclient.discovery import build

        with self._lock:  # don't refresh the same token twice in parallel
            creds = load_credentials(self._store)
        # The library ships Gmail/Calendar API descriptions, so this makes no
        # network call; cache_discovery=False avoids a noisy file-cache warning.
        return build(api, version, credentials=creds, cache_discovery=False)
