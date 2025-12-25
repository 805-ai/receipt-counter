"""
Penny Counter Implementation

Patent Reference: "CDT + Penny Counter for AI-Driven Billing and Compliance"
Patent Pending: US 63/926,683, US 63/917,247

Claims: "Upon ALLOW or DENY, minting cryptographically signed receipt and
incrementing usage counter associated with receipt. Transmitting billing
data to payment processing system (Stripe) for settlement."

Key Innovation: Every governance operation is metered and billable.

© 2025 Final Boss Technology, Inc. All rights reserved.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum
from threading import Lock
import json
import logging

logger = logging.getLogger(__name__)


class BillingTier(Enum):
    """Pricing tiers for governance operations."""
    FREE = "FREE"
    STARTER = "STARTER"
    PROFESSIONAL = "PROFESSIONAL"
    ENTERPRISE = "ENTERPRISE"


@dataclass
class UsageRecord:
    """
    A single usage record tied to a governance receipt.
    Every receipt generates a usage record for billing.
    """
    record_id: str
    receipt_id: str
    timestamp: str
    tenant_id: str
    operation_type: str
    resource_type: str
    tokens_processed: int = 0
    signature_verifications: int = 1
    storage_bytes: int = 0
    compute_ms: float = 0.0
    unit_cost_cents: float = 0.0
    total_cost_cents: float = 0.0
    billing_tier: BillingTier = BillingTier.STARTER
    settled: bool = False
    invoice_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "receipt_id": self.receipt_id,
            "timestamp": self.timestamp,
            "tenant_id": self.tenant_id,
            "operation_type": self.operation_type,
            "resource_type": self.resource_type,
            "tokens_processed": self.tokens_processed,
            "signature_verifications": self.signature_verifications,
            "storage_bytes": self.storage_bytes,
            "compute_ms": self.compute_ms,
            "unit_cost_cents": self.unit_cost_cents,
            "total_cost_cents": self.total_cost_cents,
            "billing_tier": self.billing_tier.value,
            "settled": self.settled,
            "invoice_id": self.invoice_id,
        }


@dataclass
class TenantUsage:
    """Aggregated usage for a tenant."""
    tenant_id: str
    period_start: str
    period_end: str
    total_operations: int = 0
    total_receipts: int = 0
    total_revocations: int = 0
    total_tokens: int = 0
    total_cost_cents: float = 0.0
    records: List[UsageRecord] = field(default_factory=list)


class PennyCounter:
    """
    The Penny Counter billing engine.

    Patent: "Incrementing usage counter associated with receipt.
    Transmitting billing data to payment processing system for settlement."

    Every governance operation is counted and priced.
    """

    DEFAULT_PRICING = {
        "receipt_generation": 0.01,
        "signature_verification": 0.005,
        "cdt_validation": 0.002,
        "epoch_revocation": 1.0,
        "storage_per_kb": 0.001,
        "pqc_signature": 0.05,
    }

    def __init__(
        self,
        pricing: Optional[Dict[str, float]] = None,
        tier: BillingTier = BillingTier.FREE,
    ):
        self.pricing = pricing or self.DEFAULT_PRICING.copy()
        self.tier = tier
        self._records: List[UsageRecord] = []
        self._tenant_usage: Dict[str, TenantUsage] = {}
        self._lock = Lock()
        self._counter = 0
        self._global_receipt_count = 0

        self._tier_multipliers = {
            BillingTier.FREE: 0.0,
            BillingTier.STARTER: 1.0,
            BillingTier.PROFESSIONAL: 0.8,
            BillingTier.ENTERPRISE: 0.5,
        }

    def record_operation(
        self,
        receipt_id: str,
        tenant_id: str,
        operation_type: str,
        resource_type: str = "default",
        tokens_processed: int = 0,
        signature_verifications: int = 1,
        storage_bytes: int = 0,
        compute_ms: float = 0.0,
        use_pqc: bool = False,
    ) -> UsageRecord:
        """Record a governance operation for billing."""
        with self._lock:
            self._counter += 1
            self._global_receipt_count += 1
            record_id = f"USG-{self._counter:012d}"

        unit_cost = self.pricing["receipt_generation"]
        total_cost = unit_cost

        sig_cost = (
            self.pricing["pqc_signature"] if use_pqc
            else self.pricing["signature_verification"]
        )
        total_cost += sig_cost * signature_verifications

        if storage_bytes > 0:
            total_cost += self.pricing["storage_per_kb"] * (storage_bytes / 1024)

        multiplier = self._tier_multipliers.get(self.tier, 1.0)
        total_cost *= multiplier

        record = UsageRecord(
            record_id=record_id,
            receipt_id=receipt_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            tenant_id=tenant_id,
            operation_type=operation_type,
            resource_type=resource_type,
            tokens_processed=tokens_processed,
            signature_verifications=signature_verifications,
            storage_bytes=storage_bytes,
            compute_ms=compute_ms,
            unit_cost_cents=unit_cost,
            total_cost_cents=total_cost,
            billing_tier=self.tier,
        )

        with self._lock:
            self._records.append(record)

            if tenant_id not in self._tenant_usage:
                self._tenant_usage[tenant_id] = TenantUsage(
                    tenant_id=tenant_id,
                    period_start=record.timestamp,
                    period_end=record.timestamp,
                )

            tenant = self._tenant_usage[tenant_id]
            tenant.total_operations += 1
            tenant.total_receipts += 1
            tenant.total_tokens += tokens_processed
            tenant.total_cost_cents += total_cost
            tenant.period_end = record.timestamp
            tenant.records.append(record)

        return record

    def get_global_count(self) -> int:
        """Get global receipt count."""
        with self._lock:
            return self._global_receipt_count

    def get_stats(self) -> Dict[str, Any]:
        """Get global statistics."""
        with self._lock:
            return {
                "total_receipts": self._global_receipt_count,
                "total_tenants": len(self._tenant_usage),
                "total_records": len(self._records),
                "goal": 1_000_000,
                "progress_percent": round(self._global_receipt_count / 1_000_000 * 100, 4),
            }

    def get_tenant_usage(self, tenant_id: str) -> Optional[TenantUsage]:
        """Get aggregated usage for a tenant."""
        return self._tenant_usage.get(tenant_id)


# Global instance
counter = PennyCounter(tier=BillingTier.FREE)
