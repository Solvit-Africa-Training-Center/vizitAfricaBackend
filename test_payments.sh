#!/bin/bash


# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8000/api}"
AUTH_TOKEN="$AUTH_TOKEN"
BOOKING_ID="$BOOKING_ID"

if [ -z "$AUTH_TOKEN" ] || [ -z "$BOOKING_ID" ]; then
    echo "Error: AUTH_TOKEN and BOOKING_ID must be set"
    exit 1
fi

# 1. Create Intent
echo "Step 1: Creating Payment Intent..."
RESP=$(curl -s -X POST \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"booking_id\": \"$BOOKING_ID\"}" \
  "$BASE_URL/payments/stripe/create-intent/")

echo "Response: $RESP"
PI_ID=$(echo "$RESP" | jq -r '.payment_intent_id')

if [ "$PI_ID" == "null" ] || [ -z "$PI_ID" ]; then
    echo "Failed to get payment_intent_id."
    exit 1
fi

echo "Created Payment Intent: $PI_ID"

# 2. Confirm Success
echo -e "\nStep 2: Confirming Payment..."
CONFIRM_RESP=$(curl -s -X POST \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"payment_intent_id\": \"$PI_ID\",
    \"payment_method_id\": \"tok_visa\"
  }" \
  "$BASE_URL/payments/stripe/confirm/")

echo "Confirm Response: $CONFIRM_RESP"

# 3. Refund
echo -e "\nStep 3: Refunding Payment..."
REFUND_RESP=$(curl -s -X POST \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"booking_id\": \"$BOOKING_ID\",
    \"reason\": \"requested_by_customer\"
  }" \
  "$BASE_URL/payments/stripe/refund/")

echo "Refund Response: $REFUND_RESP"
