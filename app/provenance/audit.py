"""Hash-chained audit trail for tamper-evident logging.

Each audit entry stores the hash of the previous entry, forming an append-only
chain. Any modification or deletion of a historical entry breaks the chain and
is detectable via :meth:`AuditService.verify_chain` — a key control for the
false-accusation / chain-of-custody requirements (doc section 13.4).
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditLog


def _hash_entry(prev_hash: str, actor: str, action: str, resource_id: str, detail: dict) -> str:
    payload = json.dumps(
        {
            "prev": prev_hash,
            "actor": actor,
            "action": action,
            "resource_id": resource_id,
            "detail": detail,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AuditService:
    """Append-only, hash-chained audit log."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _last_hash(self) -> str:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(1)
        last = self.session.scalars(stmt).first()
        return last.entry_hash if last else ""

    def log(
        self,
        action: str,
        actor: str = "system",
        resource_type: str = "",
        resource_id: str = "",
        detail: dict | None = None,
    ) -> AuditLog:
        """Append a new audit entry linked to the previous one."""
        detail = detail or {}
        prev = self._last_hash()
        entry_hash = _hash_entry(prev, actor, action, resource_id, detail)
        entry = AuditLog(
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            prev_hash=prev,
            entry_hash=entry_hash,
            detail=detail,
        )
        self.session.add(entry)
        self.session.flush()
        return entry

    def verify_chain(self) -> tuple[bool, int]:
        """Verify the integrity of the entire audit chain.

        Returns:
            Tuple ``(is_valid, checked_count)``. ``is_valid`` is False if any
            link's stored hash does not match a recomputation, or if the prev
            pointer does not match the actual previous entry's hash.
        """
        stmt = select(AuditLog).order_by(AuditLog.created_at.asc())
        entries = list(self.session.scalars(stmt))
        prev = ""
        for e in entries:
            if e.prev_hash != prev:
                return False, len(entries)
            expected = _hash_entry(e.prev_hash, e.actor, e.action, e.resource_id, e.detail)
            if expected != e.entry_hash:
                return False, len(entries)
            prev = e.entry_hash
        return True, len(entries)
