#!/bin/bash
# Quick smoke test for DocLens API
# Run after: docker compose up --build
# Usage: bash samples/test-api.sh

set -e
API="http://localhost:8000/api"
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "=== DocLens API Smoke Test ==="
echo ""

# 1. Health check
echo -n "1. Health check... "
HEALTH=$(curl -s $API/health)
if echo "$HEALTH" | grep -q '"postgres": true'; then
    echo -e "${GREEN}✓ Healthy${NC}"
else
    echo -e "${RED}✗ Failed${NC}: $HEALTH"
    exit 1
fi

# 2. Signup
echo -n "2. Signup... "
SIGNUP=$(curl -s -X POST $API/auth/signup \
    -H "Content-Type: application/json" \
    -d '{"email": "test@doclens.dev", "password": "testpass123"}' \
    -w "\n%{http_code}" 2>/dev/null)
HTTP_CODE=$(echo "$SIGNUP" | tail -1)
if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "409" ]; then
    echo -e "${GREEN}✓ OK${NC} (status: $HTTP_CODE)"
else
    echo -e "${RED}✗ Failed${NC} (status: $HTTP_CODE)"
fi

# 3. Login
echo -n "3. Login... "
LOGIN=$(curl -s -X POST $API/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "test@doclens.dev", "password": "testpass123"}')
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null || echo "")
if [ -n "$TOKEN" ]; then
    echo -e "${GREEN}✓ Got token${NC}"
else
    echo -e "${RED}✗ No token${NC}: $LOGIN"
    exit 1
fi

AUTH="Authorization: Bearer $TOKEN"

# 4. Upload sample document
echo -n "4. Upload document... "
UPLOAD=$(curl -s -X POST $API/documents \
    -H "$AUTH" \
    -F "file=@samples/sample-architecture.txt")
DOC_ID=$(echo "$UPLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
if [ -n "$DOC_ID" ]; then
    echo -e "${GREEN}✓ Uploaded${NC} (id: ${DOC_ID:0:8}...)"
else
    echo -e "${RED}✗ Failed${NC}: $UPLOAD"
    exit 1
fi

# 5. Wait for processing
echo -n "5. Processing... "
for i in $(seq 1 30); do
    STATUS=$(curl -s -H "$AUTH" $API/documents/$DOC_ID | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null)
    if [ "$STATUS" = "ready" ]; then
        echo -e "${GREEN}✓ Ready${NC}"
        break
    elif [ "$STATUS" = "failed" ] || [ "$STATUS" = "empty" ]; then
        echo -e "${RED}✗ $STATUS${NC}"
        exit 1
    fi
    sleep 2
done
if [ "$STATUS" = "processing" ]; then
    echo -e "${RED}✗ Timeout${NC}"
    exit 1
fi

# 6. Get chunks
echo -n "6. Get chunks... "
CHUNKS=$(curl -s -H "$AUTH" $API/documents/$DOC_ID/chunks)
CHUNK_COUNT=$(echo "$CHUNKS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['chunks']))" 2>/dev/null || echo "0")
echo -e "${GREEN}✓ $CHUNK_COUNT chunks${NC}"

# 7. Ask a question
echo -n "7. Ask question... "
ANSWER=$(curl -s -X POST $API/queries \
    -H "$AUTH" \
    -H "Content-Type: application/json" \
    -d "{\"document_id\": \"$DOC_ID\", \"question\": \"What is the total development cost?\"}")
CONFIDENCE=$(echo "$ANSWER" | python3 -c "import sys,json; print(json.load(sys.stdin)['confidence'])" 2>/dev/null || echo "")
ANSWER_TEXT=$(echo "$ANSWER" | python3 -c "import sys,json; print(json.load(sys.stdin)['answer'][:100])" 2>/dev/null || echo "")
if [ -n "$CONFIDENCE" ]; then
    echo -e "${GREEN}✓ Got answer${NC} (confidence: $CONFIDENCE)"
    echo "   → $ANSWER_TEXT..."
else
    echo -e "${RED}✗ Failed${NC}: $ANSWER"
fi

# 8. Check budget
echo -n "8. Budget status... "
BUDGET=$(curl -s -H "$AUTH" $API/budget)
REMAINING=$(echo "$BUDGET" | python3 -c "import sys,json; print(json.load(sys.stdin)['remaining_pct'])" 2>/dev/null || echo "")
if [ -n "$REMAINING" ]; then
    echo -e "${GREEN}✓ ${REMAINING}% remaining${NC}"
else
    echo -e "${RED}✗ Failed${NC}: $BUDGET"
fi

echo ""
echo -e "${GREEN}=== All checks passed! ===${NC}"
echo "Open http://localhost:5173 in your browser to use the app."
