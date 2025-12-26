#!/usr/bin/env python3
"""
Batch Receipt Generator

Generates receipts locally and submits to counter API.
Use this to quickly build toward 1M receipts.

Patent Pending: US 63/926,683, US 63/917,247
© 2025 Final Boss Technology, Inc.
"""

import argparse
import asyncio
import aiohttp
import time
from datetime import datetime

COUNTER_URL = "https://receipts.finalbosstech.com"


async def submit_batch(session: aiohttp.ClientSession, count: int, tenant_id: str):
    """Submit a batch of receipts."""
    try:
        async with session.post(
            f"{COUNTER_URL}/batch",
            json={"count": count, "tenant_id": tenant_id},
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data
            else:
                print(f"Error: {resp.status}")
                return None
    except Exception as e:
        print(f"Request failed: {e}")
        return None


async def main():
    parser = argparse.ArgumentParser(description="Batch receipt generator")
    parser.add_argument("--total", type=int, default=100_000, help="Total receipts to generate")
    parser.add_argument("--batch-size", type=int, default=10_000, help="Receipts per batch")
    parser.add_argument("--tenant", type=str, default="batch-generator", help="Tenant ID")
    parser.add_argument("--url", type=str, default=COUNTER_URL, help="Counter API URL")
    args = parser.parse_args()

    global COUNTER_URL
    COUNTER_URL = args.url

    print(f"=== Batch Receipt Generator ===")
    print(f"Target: {args.total:,} receipts")
    print(f"Batch size: {args.batch_size:,}")
    print(f"API: {COUNTER_URL}")
    print()

    start = time.time()
    generated = 0

    async with aiohttp.ClientSession() as session:
        while generated < args.total:
            batch = min(args.batch_size, args.total - generated)
            result = await submit_batch(session, batch, args.tenant)

            if result:
                generated += batch
                elapsed = time.time() - start
                rate = generated / elapsed if elapsed > 0 else 0
                remaining = args.total - generated
                eta = remaining / rate if rate > 0 else 0

                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"Generated: {generated:,} / {args.total:,} "
                      f"({result['progress_percent']:.4f}% of 1M) "
                      f"Rate: {rate:,.0f}/s "
                      f"ETA: {eta:.0f}s")
            else:
                print("Batch failed, retrying in 1s...")
                await asyncio.sleep(1)

    elapsed = time.time() - start
    print()
    print(f"=== Complete ===")
    print(f"Generated: {generated:,} receipts")
    print(f"Time: {elapsed:.1f}s")
    print(f"Rate: {generated/elapsed:,.0f} receipts/second")


if __name__ == "__main__":
    asyncio.run(main())
