"""The fake CRM client and its exceptions.

There is no real Salesforce/HubSpot here. Tests build a FakeCrm, seed it, and
pass it into create_app(crm). The service only ever calls crm.fetch(...); it
never constructs its own client. This is the injection seam described in the
assessment.
"""
from __future__ import annotations


class RateLimited(Exception):
    """Raised by the CRM when a request is throttled.

    Carries which object was throttled and how long the caller should wait
    before retrying (milliseconds).
    """

    def __init__(self, object_name: str, retry_after_ms: int):
        self.object_name = object_name
        self.retry_after_ms = retry_after_ms
        super().__init__(f"{object_name} rate limited; retry after {retry_after_ms}ms")


class CrmRecordNotFound(Exception):
    """Raised when no record exists for (object_name, record_id)."""

    def __init__(self, object_name: str, record_id: str):
        self.object_name = object_name
        self.record_id = record_id
        super().__init__(f"{object_name} record '{record_id}' not found")


class FakeCrm:
    """In-test CRM. Seed records, optionally arm a one-time rate-limit failure,
    and record every fetch call so tests can assert one call per object.
    """

    def __init__(self):
        self._records: dict[tuple[str, str], dict] = {}
        self.calls: list[dict] = []
        self._fail_once: set[str] = set()

    def seed(self, object_name: str, record_id: str, values: dict) -> None:
        self._records[(object_name, record_id)] = values

    def fail_next(self, object_name: str) -> None:
        """Next fetch of this object raises RateLimited. The one after succeeds."""
        self._fail_once.add(object_name)

    def fetch(self, object_name: str, record_id: str, fields) -> dict:
        self.calls.append({"object": object_name, "fields": list(fields)})
        if object_name in self._fail_once:
            self._fail_once.remove(object_name)
            raise RateLimited(object_name, retry_after_ms=5)
        row = self._records.get((object_name, record_id))
        if row is None:
            raise CrmRecordNotFound(object_name, record_id)
        return {field: row[field] for field in fields if field in row}
