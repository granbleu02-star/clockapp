"""윌리엄 오닐 CAN SLIM 평가.

참고: "How to Make Money in Stocks" (William J. O'Neil)

C — Current Quarterly Earnings  (분기 EPS 성장률)
A — Annual Earnings Increases   (연간 EPS 성장)
N — New Products/Highs           (신제품/52주 신고가)
S — Supply and Demand            (수급/거래량)
L — Leader or Laggard            (상대강도 70+ 권장, 80+ 이상적)
I — Institutional Sponsorship    (기관 보유)
M — Market Direction             (시장 방향)

* 가격/공개 데이터로 측정 가능한 항목 위주로 평가.
* 펀더멘털 항목(C/A/I)은 네이버 메인 페이지에서 수집 가능한 경우 사용,
  불가능한 항목은 사용자가 직접 보완할 수 있도록 표시한다.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd


def evaluate_canslim(
    price_df: pd.DataFrame,
    kospi_df: Optional[pd.DataFrame] = None,
    summary: Optional[dict] = None,
    rs_score: Optional[float] = None,
    user_fundamentals: Optional[dict] = None,
) -> dict:
    """CAN SLIM 평가.

    Args:
        price_df: 종목 일봉 OHLCV
        kospi_df: KOSPI 일봉 (M 평가용)
        summary: NaverFetcher.get_summary() 결과의 as_dict() 또는 fundamentals
        rs_score: 시장 대비 가중 RS (% 단위)
        user_fundamentals: 사용자가 직접 입력한 펀더멘털 보강 데이터.
            지원 키: q_eps_growth, a_eps_growth, institutional_ratio
    """
    user_fundamentals = user_fundamentals or {}
    criteria = []

    # ---- C: Current Quarterly Earnings ----
    q_eps_growth = user_fundamentals.get("q_eps_growth")
    if q_eps_growth is None:
        c_passed = None
        c_detail = "분기 EPS YoY 성장률 데이터 미입력. 직접 입력해 주세요."
    else:
        c_passed = q_eps_growth >= 25
        c_detail = (
            f"분기 EPS YoY {q_eps_growth:+.1f}% (기준 ≥ +25%, "
            f"이상적 ≥ +40%~+50%)"
        )
    criteria.append(
        {
            "id": "C",
            "name": "Current Quarterly Earnings (분기 EPS 성장 ≥25%)",
            "pass": c_passed,
            "detail": c_detail,
        }
    )

    # ---- A: Annual Earnings Increases ----
    a_eps_growth = user_fundamentals.get("a_eps_growth")
    if a_eps_growth is None:
        a_passed = None
        a_detail = "최근 3년 연간 EPS 성장률 데이터 미입력. 직접 입력해 주세요."
    else:
        a_passed = a_eps_growth >= 25
        a_detail = f"연간 EPS 성장 {a_eps_growth:+.1f}% (기준 ≥ +25%, 3년 연속)"
    criteria.append(
        {
            "id": "A",
            "name": "Annual Earnings (연간 EPS ≥25%, 3년)",
            "pass": a_passed,
            "detail": a_detail,
        }
    )

    # ---- N: New Highs / New Products ----
    close = price_df["close"].reset_index(drop=True)
    high = price_df["high"].reset_index(drop=True)
    current = float(close.iloc[-1])
    last_252 = high.iloc[-252:] if len(high) >= 252 else high
    high_52w = float(last_252.max())
    pct_to_high = (current / high_52w - 1) * 100
    n_passed = pct_to_high >= -5  # 52주 신고가 5% 이내
    criteria.append(
        {
            "id": "N",
            "name": "New 52-week High 근접 (≤ 5% 이내) / 신제품·실적 모멘텀",
            "pass": n_passed,
            "detail": f"52주 고점 {high_52w:,.0f} 대비 {pct_to_high:+.2f}% "
            + ("✅ 신고가권" if pct_to_high >= -5 else "(신고가 미근접)"),
        }
    )

    # ---- S: Supply and Demand (거래량 분석) ----
    volume = price_df["volume"].reset_index(drop=True)
    avg_vol_50 = float(volume.iloc[-50:].mean()) if len(volume) >= 50 else float("nan")
    today_vol = float(volume.iloc[-1])
    vol_ratio = today_vol / avg_vol_50 if avg_vol_50 > 0 else 0.0

    # 최근 5일 중 거래량 급증(50일 평균의 1.4배 이상) + 양봉 비율
    up_volume_days = 0
    if len(price_df) >= 50:
        recent = price_df.iloc[-10:]
        for _, row in recent.iterrows():
            if row["close"] > row["open"] and row["volume"] > avg_vol_50 * 1.4:
                up_volume_days += 1

    s_passed = vol_ratio >= 1.0 or up_volume_days >= 2
    criteria.append(
        {
            "id": "S",
            "name": "Supply/Demand (거래량 - 상승일 거래량 증가)",
            "pass": s_passed,
            "detail": (
                f"오늘 거래량 / 50일 평균 = {vol_ratio:.2f}배, "
                f"최근 10일 중 상승 + 거래량 급증(≥1.4x) 일수 = {up_volume_days}일"
            ),
        }
    )

    # ---- L: Leader or Laggard (RS) ----
    if rs_score is None:
        l_passed = None
        l_detail = "RS 점수 계산 불가 (벤치마크 데이터 부족)"
    else:
        l_passed = rs_score >= 0
        l_detail = (
            f"KOSPI 대비 가중 상대수익률 {rs_score:+.2f}%p "
            + ("(✅ 시장 주도주 후보)" if rs_score >= 10 else "(권장: +10%p 이상)")
        )
    criteria.append(
        {
            "id": "L",
            "name": "Leader (RS 시장 대비 강세, 70+ 권장 / +0%p 이상)",
            "pass": l_passed,
            "detail": l_detail,
        }
    )

    # ---- I: Institutional Sponsorship ----
    summary = summary or {}
    foreign = summary.get("외국인소진율(%)") or summary.get("foreign_ratio")
    institutional_ratio = user_fundamentals.get("institutional_ratio")

    if institutional_ratio is None and foreign is None:
        i_passed = None
        i_detail = "기관/외국인 보유율 데이터 없음 - 직접 확인 필요"
    else:
        # 외국인 소진율을 기관 수급의 프록시로 사용 (불완전 지표)
        proxy = institutional_ratio if institutional_ratio is not None else foreign
        i_passed = proxy >= 10  # 매우 느슨한 기준
        i_detail = (
            f"기관/외국인 보유(또는 소진) 비율 {proxy:.2f}% "
            + ("(데이터 보강 필요)" if institutional_ratio is None else "")
        )
    criteria.append(
        {
            "id": "I",
            "name": "Institutional Sponsorship (기관/외국인 보유)",
            "pass": i_passed,
            "detail": i_detail,
        }
    )

    # ---- M: Market Direction ----
    if kospi_df is not None and len(kospi_df) >= 200:
        k_close = kospi_df["close"].reset_index(drop=True)
        k_ma50 = k_close.rolling(50).mean().iloc[-1]
        k_ma200 = k_close.rolling(200).mean().iloc[-1]
        k_current = k_close.iloc[-1]
        m_passed = (k_current > k_ma50) and (k_current > k_ma200) and (k_ma50 > k_ma200)
        m_detail = (
            f"KOSPI {k_current:,.2f} / 50MA {k_ma50:,.2f} / 200MA {k_ma200:,.2f} - "
            + ("✅ 상승 추세" if m_passed else "조정/하락 추세")
        )
    else:
        m_passed = None
        m_detail = "KOSPI 데이터 부족"

    criteria.append(
        {
            "id": "M",
            "name": "Market Direction (KOSPI 추세)",
            "pass": m_passed,
            "detail": m_detail,
        }
    )

    # 집계
    decided = [c for c in criteria if c["pass"] is not None]
    pass_count = sum(1 for c in decided if c["pass"])
    pending = [c["id"] for c in criteria if c["pass"] is None]

    return {
        "valid": True,
        "pass_count": pass_count,
        "decided_total": len(decided),
        "total": len(criteria),
        "pending": pending,
        "criteria": criteria,
        "verdict": _verdict(pass_count, len(decided), pending),
    }


def _verdict(pass_count: int, decided_total: int, pending: list) -> str:
    if decided_total == 0:
        return "데이터 부족 - 평가 불가"
    ratio = pass_count / decided_total
    base = "✅ 강력 매수 후보" if ratio >= 0.85 else (
        "🟢 양호" if ratio >= 0.7 else (
            "🟡 부분 충족" if ratio >= 0.5 else "🔴 미달"
        )
    )
    if pending:
        base += f"  (미평가: {', '.join(pending)} - 직접 입력 필요)"
    return base
