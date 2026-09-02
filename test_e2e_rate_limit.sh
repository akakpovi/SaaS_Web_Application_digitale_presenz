#!/bin/bash
echo "🧪 Test E2E — Rate-limiting 5/h sur /api/v1/public/scan/"
echo "=========================================================="
for i in $(seq 1 6); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}"     -X POST http://localhost/api/v1/public/scan/     -H "Content-Type: application/json"     -d '{"url": "https://example.com"}')
  echo "Requête #$i → HTTP $STATUS"
  sleep 0.2
done
