# Receipt Counter

**Track cryptographic receipts toward 1,000,000 goal.**

## Run Locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Visit: http://localhost:8000

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Public dashboard |
| `/count` | GET | Get current count |
| `/stats` | GET | Get detailed stats |
| `/receipt` | POST | Submit a receipt |
| `/batch` | POST | Submit batch (up to 100K) |
| `/health` | GET | Health check |

## Submit a Receipt

```bash
curl -X POST http://localhost:8000/receipt \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "my-app", "operation_type": "sign"}'
```

## Batch Generator

Generate 100K receipts:

```bash
python batch_generator.py --total 100000 --url http://localhost:8000
```

## Deploy

### Vercel

```bash
vercel --prod
```

### Docker

```bash
docker build -t receipt-counter .
docker run -p 8000:8000 receipt-counter
```

### Railway

```bash
railway up
```

## Patent Notice

**Patent Pending:** US 63/926,683, US 63/917,247

The Penny Counter billing engine and cryptographic receipt architecture
are protected by pending patent applications assigned to
Final Boss Technology, Inc.

© 2025 Final Boss Technology, Inc. All rights reserved.
