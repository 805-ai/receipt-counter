"""
Penny Counter Implementation with MongoDB Persistence

Patent Reference: "CDT + Penny Counter for AI-Driven Billing and Compliance"
Patent Pending: US 63/926,683, US 63/917,247

Claims: "Upon ALLOW or DENY, minting cryptographically signed receipt and
incrementing usage counter associated with receipt. Transmitting billing
data to payment processing system (Stripe) for settlement."

Key Innovation: Every governance operation is metered and billable.

(c) 2025 Final Boss Technology, Inc. All rights reserved.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum
from threading import Lock
import os
import logging

logger = logging.getLogger(__name__)

# MongoDB connection
MONGODB_URI = os.environ.get("MONGODB_URI", "")
DB_NAME = os.environ.get("DB_NAME", "receipt_counter")

# Async MongoDB client (initialized on first request)
_mongo_client = None
_db = None


def get_db():
    """Get MongoDB database connection."""
    global _mongo_client, _db
    if _mongo_client is None and MONGODB_URI:
        from motor.motor_asyncio import AsyncIOMotorClient
        _mongo_client = AsyncIOMotorClient(MONGODB_URI)
        _db = _mongo_client[DB_NAME]
        logger.info(f"Connected to MongoDB: {DB_NAME}")
    return _db


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
    The Penny Counter billing engine with MongoDB persistence.

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
        self._initialized = False

        self._tier_multipliers = {
            BillingTier.FREE: 0.0,
            BillingTier.STARTER: 1.0,
            BillingTier.PROFESSIONAL: 0.8,
            BillingTier.ENTERPRISE: 0.5,
        }

    async def initialize(self):
        """Load count from MongoDB on startup."""
        if self._initialized:
            return

        db = get_db()
        if db is not None:
            try:
                # Get the global counter document
                counters = db["counters"]
                doc = await counters.find_one({"_id": "global"})
                if doc:
                    self._global_receipt_count = doc.get("count", 0)
                    self._counter = doc.get("record_counter", 0)
                    logger.info(f"Loaded count from MongoDB: {self._global_receipt_count}")
                else:
                    # Initialize counter document
                    await counters.insert_one({
                        "_id": "global",
                        "count": 0,
                        "record_counter": 0,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    })
                    logger.info("Initialized new counter in MongoDB")

                # Count tenants
                tenants = await db["receipts"].distinct("tenant_id")
                for tenant_id in tenants:
                    count = await db["receipts"].count_documents({"tenant_id": tenant_id})
                    self._tenant_usage[tenant_id] = TenantUsage(
                        tenant_id=tenant_id,
                        period_start="",
                        period_end="",
                        total_receipts=count,
                        total_operations=count,
                    )

                self._initialized = True
            except Exception as e:
                logger.error(f"MongoDB init error: {e}")
        else:
            logger.warning("No MONGODB_URI set - running in memory-only mode")
            self._initialized = True

    async def _persist_receipt(self, record: UsageRecord):
        """Persist a receipt to MongoDB."""
        db = get_db()
        if db is None:
            return

        try:
            # Insert receipt
            await db["receipts"].insert_one(record.to_dict())

            # Update global counter atomically
            await db["counters"].update_one(
                {"_id": "global"},
                {
                    "$inc": {"count": 1, "record_counter": 1},
                    "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"MongoDB persist error: {e}")

    async def _persist_batch(self, count: int, tenant_id: str):
        """Persist a batch count to MongoDB (without individual records)."""
        db = get_db()
        if db is None:
            return

        try:
            # Update global counter atomically
            await db["counters"].update_one(
                {"_id": "global"},
                {
                    "$inc": {"count": count, "record_counter": count},
                    "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                },
                upsert=True
            )

            # Update tenant counter
            await db["tenant_counters"].update_one(
                {"_id": tenant_id},
                {
                    "$inc": {"count": count},
                    "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"MongoDB batch persist error: {e}")

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
            # Keep only last 1000 in memory for stats
            if len(self._records) > 1000:
                self._records = self._records[-500:]
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

        return record

    def record_batch(self, count: int, tenant_id: str):
        """Record a batch of receipts (fast path for bulk generation)."""
        with self._lock:
            self._counter += count
            self._global_receipt_count += count

            if tenant_id not in self._tenant_usage:
                self._tenant_usage[tenant_id] = TenantUsage(
                    tenant_id=tenant_id,
                    period_start=datetime.now(timezone.utc).isoformat(),
                    period_end=datetime.now(timezone.utc).isoformat(),
                )

            tenant = self._tenant_usage[tenant_id]
            tenant.total_operations += count
            tenant.total_receipts += count
            tenant.period_end = datetime.now(timezone.utc).isoformat()

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
                "persistent": MONGODB_URI != "",
            }

    def get_tenant_usage(self, tenant_id: str) -> Optional[TenantUsage]:
        """Get aggregated usage for a tenant."""
        return self._tenant_usage.get(tenant_id)


# Global instance
counter = PennyCounter(tier=BillingTier.FREE)
