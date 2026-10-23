"""In-memory bookings and service requests, saved to app/data/bookings.json."""

import json
from pathlib import Path

PATH = Path(__file__).parent / "data" / "bookings.json"


class Store:
    def __init__(self, path: Path = PATH) -> None:
        self.path = path
        self.data: dict[str, list[dict]] = (
            json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        )

    def add(self, collection: str, record: dict) -> dict:
        self.data.setdefault(collection, []).append(record)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        return record

    def all(self, collection: str) -> list[dict]:
        return self.data.get(collection, [])


store = Store()
