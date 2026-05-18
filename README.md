# 한국 주식 분석기 (O'Neil & Minervini)

한국 코스피 상장 종목을 **윌리엄 오닐(CAN SLIM)** 과 **마크 미너비니(Trend Template)** 기준으로 진단하고, 보유 종목 정보를 입력해 매매 의사결정을 보조해 주는 Streamlit 웹 앱입니다.

실시간 시세 및 펀더멘털 데이터는 **네이버 금융**에서 수집합니다.

---

## 주요 기능

- 📈 **가격 차트** : 캔들 + 50/150/200일 이동평균선 + 거래량
- 🎯 **Minervini Trend Template (8가지 기준)**
  1. 현재가 > 150MA & 200MA
  2. 150MA > 200MA
  3. 200MA가 최소 1개월 이상 상승 추세 (이상: 4~5개월)
  4. 50MA > 150MA > 200MA (정배열)
  5. 현재가 > 50MA
  6. 현재가가 52주 저점 +30% 이상
  7. 현재가가 52주 고점 -25% 이내
  8. KOSPI 대비 상대강도(RS) 강세
- 💎 **William O'Neil CAN SLIM**
  - C: 분기 EPS 성장 (입력)
  - A: 연간 EPS 성장 (입력)
  - N: 52주 신고가 근접 (자동)
  - S: 상승일 거래량 증가 (자동)
  - L: KOSPI 대비 RS (자동)
  - I: 기관/외국인 보유 (자동/입력)
  - M: KOSPI 추세 (자동)
- 💼 **보유 포지션 의사결정 보조**
  - PnL, 매입원가, 평가액
  - 제안 손절가(오닐 8% 룰 + 미너비니 50MA 룰 중 보수적인 값)
  - 목표가(2R / 3R / 오닐 20%·25%)
  - 종합 액션 추천 (보유 / 추가매수 / 부분익절 / 손절 등)
- 📝 **추가 요청 메모 입력란** (의사결정 기록용)
- 🔄 **5분 캐시** + 강제 새로고침 버튼

---

## 실행 방법 (5가지 옵션)

### 옵션 A — 가장 간단한 로컬 실행 (스크립트)

```bash
./run.sh
```

가상환경 생성 → 의존성 설치 → 서버 기동까지 한 번에. 브라우저에서 `http://localhost:8501` 접속.

### 옵션 B — 수동 로컬 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

### 옵션 C — Docker (한 줄 웹 서비스)

도커가 설치되어 있으면 다음 한 줄이면 끝납니다.

```bash
docker compose up -d --build
```

브라우저에서 **`http://localhost:8501`** 접속. 중지는 `docker compose down`.

같은 네트워크의 다른 기기(휴대폰, 노트북)에서도 `http://<호스트IP>:8501` 로 접속 가능합니다.

### 옵션 D — Streamlit Community Cloud (무료 공개 호스팅) ⭐

**가장 추천**. 무료, 도메인 자동 발급, 코드 푸시하면 자동 재배포.

1. 이 레포를 GitHub에 푸시
2. <https://streamlit.io/cloud> 접속 → GitHub 로그인
3. **New app** → 이 레포 + 브랜치 + `app.py` 선택 → **Deploy**
4. 1~2분 후 `https://<your-app>.streamlit.app` 발급

설정 파일(`requirements.txt`, `runtime.txt`, `.streamlit/config.toml`)이 이미 포함되어 있어 추가 작업 불필요.

### 옵션 E — Render / Railway / Fly.io (커스텀 도메인 가능)

레포에 `Procfile`, `render.yaml`, `Dockerfile` 이 모두 포함되어 있어 어디든 배포 가능.

- **Render**: <https://render.com> → New Web Service → 레포 연결 → `render.yaml` 자동 인식
- **Railway**: <https://railway.app> → New Project → Deploy from GitHub → 자동 감지
- **Fly.io**: `fly launch` → Dockerfile 자동 감지 → `fly deploy`

---

## 사용 방법

1. 사이드바에 **종목 코드**(6자리, 예: `005930` 삼성전자)를 입력
2. (선택) **보유 수량 / 평균 매수가** 입력 → 포지션 분석 활성화
3. (선택) **분기 EPS / 연간 EPS / 기관 보유율** 입력 → CAN SLIM 평가 정밀도 향상
4. (선택) **추가 요청** 입력 → 메모 기록
5. **분석 실행** 클릭

### 예시 종목 코드

| 종목 | 코드 |
|---|---|
| 삼성전자 | 005930 |
| SK하이닉스 | 000660 |
| 현대차 | 005380 |
| LG에너지솔루션 | 373220 |
| 삼성바이오로직스 | 207940 |
| NAVER | 035420 |
| 카카오 | 035720 |

---

## 데이터 소스

- **가격 시계열**: `https://fchart.stock.naver.com/sise.nhn` (네이버 차트 XML)
- **종목 요약/펀더멘털**: `https://finance.naver.com/item/main.naver`
- **시장 벤치마크**: KOSPI 지수 일봉

> 데이터는 **5분 캐시** 됩니다. 강제 갱신은 사이드바 `🔄 강제 새로고침` 버튼.

---

## Google 스프레드시트 연동 (선택)

요청대로 네이버 금융을 1차 데이터 소스로 사용했습니다. Google 시트 연동이 추가로 필요하면:

- 구글 시트의 **`GOOGLEFINANCE`** 함수에는 한국 코스피 종목이 부분만 지원됩니다 (예: `KRX:005930`).
- 더 안정적으로는 본 앱에서 수집한 데이터를 시트에 푸시하거나, 시트의 데이터를 fetch 해 평가하도록 `stock_analyzer/fetcher.py`에 어댑터를 추가하는 방식을 권장합니다.
- 필요하면 요청해 주세요. 시트 ID 와 인증 방식(서비스 계정 키)을 알려주시면 `gspread` 기반 어댑터를 추가합니다.

---

## 손절/익절 룰

- **손절**: `max(매수가 * 0.92, 50MA * 0.98)` (오닐 8% 룰 + 미너비니 50일선 룰)
- **익절**:
  - 2R / 3R (= 매수가 + 2~3 × 위험)
  - 오닐 20% / 25% 룰
- 액션 추천 트리거:
  - 손실 ≤ -8% → 손절
  - Stage 4 → 비중 축소
  - Stage 3 → 트레일링 스탑
  - Stage 2 + 미너비니 ≥ 85% & CAN SLIM ≥ 70% → 보유/추가매수
  - 수익 ≥ 20% + 기준 약화 → 부분 익절
  - 수익 ≥ 25% → 트레일링 스탑/부분 익절

---

## 디스클레이머

본 도구는 **학습·연구 목적**의 의사결정 보조 도구입니다.  
실제 매매 결과에 대한 책임은 사용자 본인에게 있습니다.

네이버 금융의 비공식 데이터 엔드포인트를 사용하므로, 사용자가 과도한 요청을 보내면 일시 차단될 수 있습니다.

---

## 프로젝트 구조

```
clockapp/
├── app.py                       # Streamlit 메인 앱
├── stock_analyzer/
│   ├── __init__.py
│   ├── fetcher.py               # 네이버 금융 수집 (가격/요약/벤치마크)
│   ├── minervini.py             # Minervini Trend Template 평가
│   ├── oneil.py                 # CAN SLIM 평가
│   └── decision.py              # 보유 포지션 의사결정 가이드
├── requirements.txt
├── .gitignore
└── README.md
```
