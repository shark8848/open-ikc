#!/usr/bin/env bash

set -euo pipefail

MODE="${1:-static}"
PORT="${OPEN_PLATFORM_PORT:-18000}"

export OPEN_PLATFORM_AUTH_MODE="$MODE"

case "$MODE" in
  static)
    : "${OPEN_PLATFORM_TOKEN:=test-token}"
    export OPEN_PLATFORM_TOKEN
    ;;
  gateway_header)
    : "${OPEN_PLATFORM_GATEWAY_REQUIRE_BEARER:=false}"
    export OPEN_PLATFORM_GATEWAY_REQUIRE_BEARER
    ;;
  oidc_jwt)
    : "${OPEN_PLATFORM_OIDC_JWKS_URL:=https://idp.example.com/.well-known/jwks.json}"
    : "${OPEN_PLATFORM_OIDC_ISSUER:=https://idp.example.com}"
    : "${OPEN_PLATFORM_OIDC_AUDIENCE:=open-ikc-api}"
    export OPEN_PLATFORM_OIDC_JWKS_URL OPEN_PLATFORM_OIDC_ISSUER OPEN_PLATFORM_OIDC_AUDIENCE
    ;;
  oauth2_introspection)
    : "${OPEN_PLATFORM_OAUTH2_INTROSPECTION_URL:=https://idp.example.com/oauth2/introspect}"
    export OPEN_PLATFORM_OAUTH2_INTROSPECTION_URL
    ;;
  *)
    echo "Unsupported auth mode: $MODE"
    echo "Usage: bash scripts/start_open_platform_auth_mode.sh [static|gateway_header|oidc_jwt|oauth2_introspection]"
    exit 1
    ;;
esac

echo "Starting Open IKC API with OPEN_PLATFORM_AUTH_MODE=$OPEN_PLATFORM_AUTH_MODE on port $PORT"
python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --reload
