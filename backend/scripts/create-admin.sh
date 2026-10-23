#!/usr/bin/env bash
# 본사(ADMIN) 계정 생성 — 회원가입 API로 계정을 만든 뒤 DB에서 role만 ADMIN으로 바꾼다.
# (회원가입은 항상 USER라서 본사 계정은 이 스크립트로만 만든다)
#
# 사용법:
#   ./scripts/create-admin.sh <username> <이름> [직책]
#   비밀번호는 실행 중에 입력 (화면 · 셸 기록에 남지 않음)
#
# 환경변수:
#   BASE_URL  백엔드 주소 (기본 http://localhost:8080, 프록시 경유 시 http://realshoot/backend)
#   ENV_FILE  DB 접속 정보가 든 .env (기본 저장소 루트의 .env)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${ENV_FILE:-$BACKEND_DIR/../.env}"
BASE_URL="${BASE_URL:-http://localhost:8080}"

if [[ $# -lt 2 ]]; then
  echo "사용법: $0 <username> <이름> [직책]" >&2
  exit 1
fi
USERNAME="$1"
CLIENT_NAME="$2"
POSITION="${3:-상담원}"
COMPANY_NAME="${COMPANY_NAME:-본사}"

# SQL에 그대로 들어가므로 회원가입 규칙과 같은 형식만 허용
if [[ ! "$USERNAME" =~ ^[A-Za-z0-9_]{4,50}$ ]]; then
  echo "username은 4~50자, 영문 · 숫자 · _만 사용할 수 있습니다." >&2
  exit 1
fi

read -r -s -p "비밀번호 (8~64자): " PASSWORD
echo
read -r -s -p "비밀번호 확인: " PASSWORD_CONFIRM
echo
if [[ "$PASSWORD" != "$PASSWORD_CONFIRM" ]]; then
  echo "비밀번호가 일치하지 않습니다." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

json_escape() { python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"; }

echo "1) 회원가입: $USERNAME"
BODY=$(printf '{"username":%s,"password":%s,"clientName":%s,"companyName":%s,"position":%s}' \
  "$(json_escape "$USERNAME")" "$(json_escape "$PASSWORD")" "$(json_escape "$CLIENT_NAME")" \
  "$(json_escape "$COMPANY_NAME")" "$(json_escape "$POSITION")")
STATUS=$(curl -s -o /dev/stderr -w '%{http_code}' -X POST "$BASE_URL/api/auth/signup" \
  -H 'Content-Type: application/json' --data-binary @- <<<"$BODY")
if [[ "$STATUS" != "201" ]]; then
  echo
  echo "회원가입 실패 (HTTP $STATUS)" >&2
  exit 1
fi

echo "2) role → ADMIN"
docker compose -f "$BACKEND_DIR/docker-compose.yml" --env-file "$ENV_FILE" exec -T \
  -e MYSQL_PWD="$MYSQL_PASSWORD" mariadb \
  mariadb -u"$MYSQL_USER" "$MYSQL_DATABASE" \
  -e "UPDATE users SET role = 'ADMIN' WHERE username = '$USERNAME'; SELECT id, username, role FROM users WHERE username = '$USERNAME';"

echo "완료: $USERNAME 으로 로그인하면 role = ADMIN"
