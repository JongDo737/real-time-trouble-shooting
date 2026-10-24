#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
RAG_DIR="$ROOT_DIR/rag_pipeline"
FAISS_DIR="$RAG_DIR/faiss_db"
VOICE_DIR="$ROOT_DIR/voice"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$ROOT_DIR"

if [ -d "$FAISS_DIR" ]; then
  echo "faiss_db 가 있어 FAISS 빌드를 건너뜁니다: $FAISS_DIR"
else
  if [ ! -d ".venv" ]; then
    echo "[1/4] 가상환경 생성: $ROOT_DIR/.venv"
    "$PYTHON_BIN" -m venv .venv
  else
    echo "[1/4] 가상환경 있음: $ROOT_DIR/.venv"
  fi

  echo "[2/4] 가상환경 활성화"
  # shellcheck disable=SC1091
  source .venv/bin/activate

  echo "[3/4] 패키지 설치"
  pip install -U pip setuptools wheel
  pip install -r "$RAG_DIR/requirements-e.txt"
  pip install -r "$VOICE_DIR/requirements.txt"

  if [ -f "$ROOT_DIR/.env" ]; then
    export OPENAI_API_KEY="$(grep '^OPENAI_API_KEY=' "$ROOT_DIR/.env" | cut -d= -f2-)"
  fi

  echo "[4/4] FAISS 빌드"
  python "$RAG_DIR/build_faiss.py"
fi

echo "[5/6] backend gradle 빌드"
cd "$ROOT_DIR/backend"
chmod +x ./gradlew
./gradlew build
cd "$ROOT_DIR"

echo "[5/6] frontend npm 빌드"
cd "$ROOT_DIR/frontend"
npm install
npm run build
cd "$ROOT_DIR"

echo "[6/6] docker compose 실행"
# docker compose 명령은 여기에 넣으면 됩니다.
