"""Evidence platform: signed forensic / legal / audit reports.

Generates tamper-evident evidence reports from trace results, suitable for legal
proceedings. Each report is signed (Ed25519) so its integrity can be verified
independently, supporting the false-accusation defences in doc section 13.4.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.tracking_engine import TraceResult
from app.payload import crypto
from app.payload.keystore import get_key_provider
from app.provenance.audit import AuditService


@dataclass
class EvidenceReport:
    """A signed evidence report bundle."""

    report_type: str
    generated_at: str
    trace: dict
    audit_chain_valid: bool
    chain_of_custody: list[str]
    statements: list[str] = field(default_factory=list)
    signature: str = ""
    public_key: str = ""

    def signing_bytes(self) -> bytes:
        d = {
            "report_type": self.report_type,
            "generated_at": self.generated_at,
            "trace": self.trace,
            "audit_chain_valid": self.audit_chain_valid,
            "chain_of_custody": self.chain_of_custody,
            "statements": self.statements,
        }
        return json.dumps(d, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def to_dict(self) -> dict:
        return {
            "report_type": self.report_type,
            "generated_at": self.generated_at,
            "trace": self.trace,
            "audit_chain_valid": self.audit_chain_valid,
            "chain_of_custody": self.chain_of_custody,
            "statements": self.statements,
            "signature": self.signature,
            "public_key": self.public_key,
        }


class EvidenceService:
    """Builds and verifies signed evidence reports."""

    def __init__(self, session: Session, now: dt.datetime | None = None) -> None:
        self.session = session
        self.audit = AuditService(session)
        handle = get_key_provider().get_master_key()
        self._keypair = crypto.SignatureKeyPair.from_master(handle.material, "evidence:sign:v1")
        self._now = now

    def _timestamp(self) -> str:
        # Caller may inject a deterministic timestamp; else use UTC now.
        return (self._now or dt.datetime.now(dt.timezone.utc)).isoformat()

    def generate(
        self,
        trace: TraceResult,
        report_type: str = "forensic",
        timestamp: str | None = None,
    ) -> EvidenceReport:
        """Generate a signed evidence report from a trace result.

        Args:
            trace: The trace result to document.
            report_type: ``forensic`` | ``legal`` | ``audit``.
            timestamp: Optional ISO timestamp (else now).

        Returns:
            A signed EvidenceReport.
        """
        audit_valid, _ = self.audit.verify_chain()
        statements = self._statements(trace, audit_valid)
        report = EvidenceReport(
            report_type=report_type,
            generated_at=timestamp or self._timestamp(),
            trace=trace.to_dict(),
            audit_chain_valid=audit_valid,
            chain_of_custody=trace.trace_path,
            statements=statements,
            public_key=self._keypair.public_bytes.hex(),
        )
        report.signature = crypto.sign(self._keypair.private_bytes, report.signing_bytes()).hex()

        self._persist(report, trace)
        self.audit.log(
            "evidence.generate",
            actor="evidence-service",
            resource_type="evidence",
            resource_id=trace.detail.get("trace_id", ""),
            detail={"report_type": report_type, "found": trace.found},
        )
        return report

    def verify(self, report: EvidenceReport, public_key: bytes | None = None) -> bool:
        """Verify a report's Ed25519 signature."""
        pub = public_key or bytes.fromhex(report.public_key)
        try:
            sig = bytes.fromhex(report.signature)
        except ValueError:
            return False
        return crypto.verify(pub, report.signing_bytes(), sig)

    def _statements(self, trace: TraceResult, audit_valid: bool) -> list[str]:
        out: list[str] = []
        if trace.found:
            out.append(
                f"A watermark embedded with model '{trace.watermark_model}' was recovered "
                f"with confidence {trace.confidence:.2%}."
            )
            out.append(
                f"The recovered token resolves in the registry to delivery "
                f"'{trace.delivery_id}' issued to recipient '{trace.recipient_id}'."
            )
            if trace.signature_valid:
                out.append("The payload's cryptographic signature is valid (non-repudiation).")
            out.append("Chain of custody: " + " -> ".join(trace.trace_path) + ".")
        else:
            out.append("No watermark attributable to a registered delivery was recovered.")
        out.append(
            "The append-only audit trail integrity check "
            + ("passed." if audit_valid else "FAILED — evidence may be compromised.")
        )
        return out

    def _persist(self, report: EvidenceReport, trace: TraceResult) -> None:
        from app.db.models import EvidenceReport as EvidenceRow

        row = EvidenceRow(
            trace_id=trace.detail.get("trace_id"),
            report_type=report.report_type,
            signature=report.signature,
            summary={"found": trace.found, "recipient": trace.recipient_id},
        )
        self.session.add(row)
        self.session.flush()
