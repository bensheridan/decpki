"""BFF-side trust bundle loader with background refresh."""
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from decpki.bundle import deserialise_bundle


class BundleCache:
    def __init__(
        self,
        bundle_path: str | None = None,
        refresh_interval_seconds: int | None = None,
    ):
        self._path = bundle_path or os.environ.get("BUNDLE_PATH", "/tmp/bundle.cbor")
        self._interval = refresh_interval_seconds or int(
            os.environ.get("BUNDLE_REFRESH_INTERVAL", "300")
        )
        self._bundle = None
        self._lock = threading.Lock()

    def _load(self):
        try:
            data = Path(self._path).read_bytes()
            bundle = deserialise_bundle(data)
            with self._lock:
                self._bundle = bundle
        except Exception as exc:
            print(f"[bundle_cache] failed to load {self._path}: {exc}", flush=True)

    def start(self):
        self._load()

        def _loop():
            while True:
                time.sleep(self._interval)
                self._load()

        t = threading.Thread(target=_loop, daemon=True, name="bundle-cache-refresh")
        t.start()

    def get_did(self, did: str):
        with self._lock:
            if self._bundle is None:
                return None
            for record in self._bundle.identities:
                if record.did == did and record.revoked_at is None:
                    return record
        return None

    def is_did_active(self, did: str) -> bool:
        return self.get_did(did) is not None
