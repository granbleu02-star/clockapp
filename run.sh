#!/usr/bin/env bash
# 한국 주식 분석기 — 로컬 웹 실행 스크립트
# 사용: ./run.sh    (포트 변경: PORT=8888 ./run.sh)
set -e

PORT="${PORT:-8501}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 가 필요합니다. https://www.python.org/downloads/ 에서 설치하세요."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "[INFO] 가상환경 .venv 생성 중..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[INFO] 의존성 설치 중..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "[INFO] 브라우저에서 http://localhost:${PORT} 으로 접속하세요."
exec streamlit run app.py \
  --server.port="${PORT}" \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --browser.gatherUsageStats=false
