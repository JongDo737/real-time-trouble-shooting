#!/usr/bin/env bash
# REST 흐름 확인: 고객 가입 · 로그인 → 통화 요청 → 본사 받기 → 해결방법 → 상세 → 종료
# 미리 본사 계정이 있어야 한다 (scripts/create-admin.sh).
#
# 사용법: ADMIN_USER=... ADMIN_PASSWORD=... ./scripts/smoke.sh
#   BASE_URL  기본 http://localhost:8080 (프록시 경유 시 http://realshoot/backend)
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
: "${ADMIN_USER:?ADMIN_USER 필요}"
: "${ADMIN_PASSWORD:?ADMIN_PASSWORD 필요}"

CUSTOMER="smoke_$(date +%s)"
CUSTOMER_PASSWORD="smoke-password-1"

req() { # method path [token] [body]
  local method="$1" path="$2" token="${3:-}" body="${4:-}"
  local args=(-s -w '\n%{http_code}' -X "$method" "$BASE_URL$path" -H 'Content-Type: application/json')
  [[ -n "$token" ]] && args+=(-H "Authorization: Bearer $token")
  [[ -n "$body" ]] && args+=(--data-binary "$body")
  curl "${args[@]}"
}

check() { # 이름 기대코드 응답
  local name="$1" expected="$2" response="$3"
  local code="${response##*$'\n'}" body="${response%$'\n'*}"
  if [[ "$code" == "$expected" ]]; then
    echo "OK   $name ($code)"
  else
    echo "FAIL $name: 기대 $expected, 실제 $code — $body" >&2
    exit 1
  fi
  LAST_BODY="$body"
}

json() { python3 -c 'import json,sys; d=json.load(sys.stdin); print(eval("d"+sys.argv[1]))' "$1" <<<"$LAST_BODY"; }

# macOS 기본 bash(3.2)에서 $( ) 안의 "{...}"가 쪼개지지 않도록 본문은 printf로 미리 만든다
SIGNUP_BODY=$(printf '{"username":"%s","password":"%s","clientName":"Smoke","companyName":"ACME US","position":"Engineer"}' \
  "$CUSTOMER" "$CUSTOMER_PASSWORD")
LOGIN_BODY=$(printf '{"username":"%s","password":"%s"}' "$CUSTOMER" "$CUSTOMER_PASSWORD")
WRONG_LOGIN_BODY=$(printf '{"username":"%s","password":"wrong-password"}' "$CUSTOMER")
ADMIN_LOGIN_BODY=$(printf '{"username":"%s","password":"%s"}' "$ADMIN_USER" "$ADMIN_PASSWORD")

check "A-1 고객 회원가입" 201 "$(req POST /api/auth/signup '' "$SIGNUP_BODY")"
check "A-1 중복 아이디" 409 "$(req POST /api/auth/signup '' "$SIGNUP_BODY")"
check "A-1 검증 오류" 422 "$(req POST /api/auth/signup '' '{"username":"a"}')"

check "A-2 고객 로그인" 200 "$(req POST /api/auth/login '' "$LOGIN_BODY")"
USER_TOKEN=$(json "['accessToken']")
check "A-2 비밀번호 오류" 401 "$(req POST /api/auth/login '' "$WRONG_LOGIN_BODY")"
check "A-2 본사 로그인" 200 "$(req POST /api/auth/login '' "$ADMIN_LOGIN_BODY")"
ADMIN_TOKEN=$(json "['accessToken']")
[[ "$(json "['user']['role']")" == "ADMIN" ]] || { echo "FAIL 본사 계정 role이 ADMIN이 아님" >&2; exit 1; }

check "토큰 없음" 401 "$(req GET /api/calls)"
check "C-1 통화 요청" 201 "$(req POST /api/calls "$USER_TOKEN" \
  '{"equipmentName":"CNC-500","errorCode":"E-1042","symptom":"The cooling fan is not spinning."}')"
CALL_ID=$(json "['callId']")
check "C-1 중복 요청" 409 "$(req POST /api/calls "$USER_TOKEN" '{"equipmentName":"CNC-500","errorCode":"E-1042"}')"
check "C-1 본사는 요청 불가" 403 "$(req POST /api/calls "$ADMIN_TOKEN" '{"equipmentName":"CNC-500","errorCode":"E-1042"}')"

check "C-2 본사 대기 목록" 200 "$(req GET '/api/calls?status=PENDING' "$ADMIN_TOKEN")"
check "C-2 고객 본인 목록" 200 "$(req GET /api/calls "$USER_TOKEN")"
[[ "$(json "['totalElements']")" == "1" ]] || { echo "FAIL 고객 목록은 본인 통화 1건이어야 함" >&2; exit 1; }
check "C-2 잘못된 status" 422 "$(req GET '/api/calls?status=FOO' "$USER_TOKEN")"

check "C-5 받기 전" 403 "$(req GET "/api/calls/$CALL_ID/solution" "$ADMIN_TOKEN")"
check "C-4 고객은 받기 불가" 403 "$(req PATCH "/api/calls/$CALL_ID/status" "$USER_TOKEN" '{"status":"CALLING"}')"
check "C-4 잘못된 status" 422 "$(req PATCH "/api/calls/$CALL_ID/status" "$ADMIN_TOKEN" '{"status":"MISSED"}')"
check "C-4 받기" 200 "$(req PATCH "/api/calls/$CALL_ID/status" "$ADMIN_TOKEN" '{"status":"CALLING"}')"
check "C-4 다시 받기" 409 "$(req PATCH "/api/calls/$CALL_ID/status" "$ADMIN_TOKEN" '{"status":"CALLING"}')"

check "C-5 해결방법" 200 "$(req GET "/api/calls/$CALL_ID/solution" "$ADMIN_TOKEN")"
echo "     status=$(json "['status']")"
check "C-5 고객은 조회 불가" 403 "$(req GET "/api/calls/$CALL_ID/solution" "$USER_TOKEN")"

check "C-3 고객 상세" 200 "$(req GET "/api/calls/$CALL_ID" "$USER_TOKEN")"
check "C-3 본사 상세" 200 "$(req GET "/api/calls/$CALL_ID" "$ADMIN_TOKEN")"
check "C-3 없는 통화" 404 "$(req GET /api/calls/00000000-0000-0000-0000-000000000000 "$ADMIN_TOKEN")"

check "C-4 종료" 200 "$(req PATCH "/api/calls/$CALL_ID/status" "$ADMIN_TOKEN" '{"status":"RESOLVED"}')"
check "C-4 종료 후 다시 종료" 409 "$(req PATCH "/api/calls/$CALL_ID/status" "$ADMIN_TOKEN" '{"status":"UNRESOLVED"}')"
check "A-3 로그아웃" 204 "$(req POST /api/auth/logout "$USER_TOKEN")"

echo "전체 통과 (callId=$CALL_ID)"
