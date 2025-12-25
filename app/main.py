"""
Receipt Counter API

Tracks receipts toward 1,000,000 goal.
Patent Pending: US 63/926,683, US 63/917,247

© 2025 Final Boss Technology, Inc. All rights reserved.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
import uuid
import os

from .penny_counter import counter


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize MongoDB connection on startup."""
    await counter.initialize()
    yield


app = FastAPI(
    title="Receipt Counter",
    description="Track cryptographic receipts toward 1M goal",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReceiptSubmission(BaseModel):
    """A receipt submission."""
    receipt_id: Optional[str] = None
    tenant_id: Optional[str] = "public"
    operation_type: Optional[str] = "sign"
    message: Optional[str] = None
    signer: Optional[str] = None
    signature: Optional[str] = None


class BatchSubmission(BaseModel):
    """Batch receipt submission."""
    count: int
    tenant_id: Optional[str] = "batch"


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Public dashboard showing receipt count."""
    stats = counter.get_stats()

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Receipt Counter - Road to 1M</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                color: #fff;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 2rem;
            }}
            .container {{ text-align: center; max-width: 800px; }}
            h1 {{ font-size: 2.5rem; margin-bottom: 0.5rem; }}
            .subtitle {{ color: #888; margin-bottom: 2rem; }}
            .counter {{
                font-size: 5rem;
                font-weight: bold;
                background: linear-gradient(90deg, #00d9ff, #00ff88);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin: 1rem 0;
            }}
            .goal {{ color: #888; font-size: 1.2rem; margin-bottom: 2rem; }}
            .progress-bar {{
                width: 100%;
                height: 30px;
                background: #333;
                border-radius: 15px;
                overflow: hidden;
                margin: 1rem 0;
            }}
            .progress-fill {{
                height: 100%;
                background: linear-gradient(90deg, #00d9ff, #00ff88);
                width: {stats['progress_percent']}%;
                transition: width 0.5s ease;
            }}
            .stats {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 1rem;
                margin-top: 2rem;
            }}
            .stat {{
                background: rgba(255,255,255,0.1);
                padding: 1rem;
                border-radius: 10px;
            }}
            .stat-value {{ font-size: 1.5rem; font-weight: bold; }}
            .stat-label {{ color: #888; font-size: 0.9rem; }}
            .cta {{
                margin-top: 2rem;
                padding: 1rem 2rem;
                background: linear-gradient(90deg, #00d9ff, #00ff88);
                color: #000;
                text-decoration: none;
                border-radius: 25px;
                font-weight: bold;
                display: inline-block;
            }}
            .patent {{ color: #666; font-size: 0.8rem; margin-top: 3rem; }}
            code {{
                background: rgba(255,255,255,0.1);
                padding: 0.5rem 1rem;
                border-radius: 5px;
                display: block;
                margin: 1rem auto;
                max-width: 600px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🧾 Receipt Counter</h1>
            <p class="subtitle">Cryptographic receipts signed worldwide</p>

            <div class="counter">{stats['total_receipts']:,}</div>
            <div class="goal">Goal: 1,000,000 receipts</div>

            <div class="progress-bar">
                <div class="progress-fill"></div>
            </div>
            <p>{stats['progress_percent']}% complete</p>

            <div class="stats">
                <div class="stat">
                    <div class="stat-value">{stats['total_tenants']}</div>
                    <div class="stat-label">Sources</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{1_000_000 - stats['total_receipts']:,}</div>
                    <div class="stat-label">Remaining</div>
                </div>
                <div class="stat">
                    <div class="stat-value">∞</div>
                    <div class="stat-label">Velocity</div>
                </div>
            </div>

            <code>npx receipt-cli-eth sign "your message" --out receipt.json</code>
            <code>pip install git+https://github.com/805-ai/langchain-receipts.git</code>

            <a href="https://github.com/805-ai/receipt-cli" class="cta">Get the CLI →</a>

            <p class="patent">
                Patent Pending: US 63/926,683, US 63/917,247<br>
                © 2025 Final Boss Technology, Inc.
            </p>
        </div>

        <script>
            // Auto-refresh every 10 seconds
            setTimeout(() => location.reload(), 10000);
        </script>
    </body>
    </html>
    """
    return html


@app.get("/count")
async def get_count():
    """Get current receipt count."""
    return {"count": counter.get_global_count(), "goal": 1_000_000}


@app.get("/stats")
async def get_stats():
    """Get detailed statistics."""
    return counter.get_stats()


@app.post("/receipt")
async def submit_receipt(submission: ReceiptSubmission):
    """
    Submit a receipt to be counted.

    This endpoint is called by CLIs and integrations.
    """
    receipt_id = submission.receipt_id or f"RCP-{uuid.uuid4().hex[:16]}"

    record = counter.record_operation(
        receipt_id=receipt_id,
        tenant_id=submission.tenant_id or "public",
        operation_type=submission.operation_type or "sign",
        resource_type="receipt",
    )

    return {
        "counted": True,
        "record_id": record.record_id,
        "total_receipts": counter.get_global_count(),
        "progress_percent": counter.get_stats()["progress_percent"],
    }


@app.post("/batch")
async def submit_batch(batch: BatchSubmission, background_tasks: BackgroundTasks):
    """
    Submit multiple receipts at once.

    For batch generators and load testing.
    """
    if batch.count > 100_000:
        raise HTTPException(status_code=400, detail="Max 100,000 per batch")

    tenant_id = batch.tenant_id or "batch"

    # Fast in-memory update
    counter.record_batch(batch.count, tenant_id)

    # Persist to MongoDB in background
    background_tasks.add_task(counter._persist_batch, batch.count, tenant_id)

    return {
        "counted": batch.count,
        "total_receipts": counter.get_global_count(),
        "progress_percent": counter.get_stats()["progress_percent"],
    }


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "receipts": counter.get_global_count()}
