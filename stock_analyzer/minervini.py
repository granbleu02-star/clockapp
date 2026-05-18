"""Mark Minervini Trend Template 평가.

참고: "Trade Like a Stock Market Wizard" (Mark Minervini)
종목이 Stage 2 상승 추세에 있는지 확인하는 8가지 가격 기준.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd


def evaluate_minervini(price_df: pd.DataFrame, rs_score: Optional[float] = None) -> dict:
    """미너비니 Trend Template 평가.

    Args:
        price_df: 일봉 OHLCV 데이터 (최소 200거래일 필요, 252거래일 권장)
        rs_score: 시장 대비 상대강도 점수 (% 단위). 음수면 시장 약세 대비.

    Returns:
        dict: 평가 결과
            - valid: 평가 가능 여부
            - pass_count / total: 통과 개수
            - criteria: 각 기준별 결과 리스트
            - metrics: 핵심 지표 값
            - stage: Stage 분류 (1/2/3/4 추정)
    """
    if price_df is None or len(price_df) < 200:
        return {
            "valid": False,
            "error": f"데이터 부족: {len(price_df) if price_df is not None else 0}일 (200일 이상 필요)",
            "pass_count": 0,
            "total": 8,
            "criteria": [],
        }

    close = price_df["close"].reset_index(drop=True)
    current = float(close.iloc[-1])

    ma50 = close.rolling(50).mean()
    ma150 = close.rolling(150).mean()
    ma200 = close.rolling(200).mean()

    cur_ma50 = float(ma50.iloc[-1])
    cur_ma150 = float(ma150.iloc[-1])
    cur_ma200 = float(ma200.iloc[-1])

    # 200일선 상승 추세 (최소 1개월=20거래일, 이상적: 4-5개월)
    ma200_20d_ago = float(ma200.iloc[-21]) if len(ma200) > 21 else float("nan")
    ma200_100d_ago = float(ma200.iloc[-101]) if len(ma200) > 101 else None
    ma200_uptrend_1m = pd.notna(ma200_20d_ago) and cur_ma200 > ma200_20d_ago
    ma200_uptrend_5m = ma200_100d_ago is not None and cur_ma200 > ma200_100d_ago

    last_252 = close.iloc[-252:] if len(close) >= 252 else close
    high_52w = float(last_252.max())
    low_52w = float(last_252.min())

    pct_from_low = (current / low_52w - 1) * 100 if low_52w > 0 else 0.0
    pct_from_high = (current / high_52w - 1) * 100 if high_52w > 0 else 0.0  # 음수면 고점 아래

    criteria = [
        {
            "id": 1,
            "name": "현재가 > 150일선 AND 현재가 > 200일선",
            "pass": current > cur_ma150 and current > cur_ma200,
            "detail": (
                f"현재가 {current:,.0f} / 150MA {cur_ma150:,.0f} / 200MA {cur_ma200:,.0f}"
            ),
        },
        {
            "id": 2,
            "name": "150일선 > 200일선",
            "pass": cur_ma150 > cur_ma200,
            "detail": f"150MA {cur_ma150:,.0f} vs 200MA {cur_ma200:,.0f} "
            f"(차이 {(cur_ma150/cur_ma200 - 1)*100:+.2f}%)",
        },
        {
            "id": 3,
            "name": "200일선이 최소 1개월 이상 상승 추세 (이상: 4-5개월)",
            "pass": ma200_uptrend_1m,
            "detail": (
                f"현재 200MA {cur_ma200:,.0f} / 20일 전 {ma200_20d_ago:,.0f}"
                + (f" / 100일 전 {ma200_100d_ago:,.0f}" if ma200_100d_ago else "")
                + (" ✅5개월 상승" if ma200_uptrend_5m else "")
            ),
        },
        {
            "id": 4,
            "name": "50일선 > 150일선 > 200일선 (정배열)",
            "pass": cur_ma50 > cur_ma150 > cur_ma200,
            "detail": f"50MA {cur_ma50:,.0f} > 150MA {cur_ma150:,.0f} > 200MA {cur_ma200:,.0f}",
        },
        {
            "id": 5,
            "name": "현재가 > 50일선",
            "pass": current > cur_ma50,
            "detail": f"현재가 {current:,.0f} vs 50MA {cur_ma50:,.0f} "
            f"({(current/cur_ma50 - 1)*100:+.2f}%)",
        },
        {
            "id": 6,
            "name": "현재가가 52주 저점에서 최소 30% 이상 상승",
            "pass": pct_from_low >= 30,
            "detail": f"52주 저점 {low_52w:,.0f} 대비 +{pct_from_low:.1f}%",
        },
        {
            "id": 7,
            "name": "현재가가 52주 고점의 25% 이내 (즉 고점 대비 -25% 이상)",
            "pass": pct_from_high >= -25,
            "detail": f"52주 고점 {high_52w:,.0f} 대비 {pct_from_high:+.1f}%",
        },
    ]

    if rs_score is not None:
        criteria.append(
            {
                "id": 8,
                "name": "상대강도(RS) 시장 대비 강세 (≥0, 이상: 큰 폭)",
                "pass": rs_score >= 0,
                "detail": f"시장 대비 가중 RS {rs_score:+.2f}%p "
                + ("✅" if rs_score >= 10 else "(권장: 10%p 이상)"),
            }
        )
    else:
        criteria.append(
            {
                "id": 8,
                "name": "상대강도(RS) 시장 대비 강세",
                "pass": False,
                "detail": "벤치마크(KOSPI) 데이터 없음 - 측정 불가",
            }
        )

    pass_count = sum(1 for c in criteria if c["pass"])

    # Stage 분류 (간이)
    stage = _classify_stage(
        current=current,
        ma50=cur_ma50,
        ma150=cur_ma150,
        ma200=cur_ma200,
        ma200_uptrend=ma200_uptrend_1m,
    )

    return {
        "valid": True,
        "pass_count": pass_count,
        "total": len(criteria),
        "criteria": criteria,
        "metrics": {
            "current": current,
            "ma50": cur_ma50,
            "ma150": cur_ma150,
            "ma200": cur_ma200,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "pct_from_low": pct_from_low,
            "pct_from_high": pct_from_high,
            "ma200_uptrend_5m": ma200_uptrend_5m,
        },
        "stage": stage,
        "verdict": _verdict(pass_count, len(criteria), stage),
    }


def _classify_stage(current, ma50, ma150, ma200, ma200_uptrend) -> str:
    """Stan Weinstein/Minervini 스타일 Stage 분류 (간이)."""
    if current > ma50 > ma150 > ma200 and ma200_uptrend:
        return "Stage 2 (상승)"
    if current < ma50 < ma150 < ma200 and not ma200_uptrend:
        return "Stage 4 (하락)"
    if current > ma200 and not (current > ma50 > ma150 > ma200):
        return "Stage 1 (바닥 다지기) 추정"
    return "Stage 3 (분배/전환) 추정"


def _verdict(pass_count: int, total: int, stage: str) -> str:
    ratio = pass_count / total
    if ratio >= 1.0:
        return "✅ 모든 기준 통과 - 미너비니식 강세 진입 가능 구간"
    if ratio >= 0.75 and "Stage 2" in stage:
        return "🟢 양호 - 추세 추종 매수 후보"
    if ratio >= 0.5:
        return "🟡 부분 충족 - 추가 확인 필요"
    return "🔴 미달 - 매수 자제"
