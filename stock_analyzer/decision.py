"""보유 종목 정보와 평가 결과를 결합해 의사결정 가이드를 생성한다.

미너비니의 손절 원칙(평균 -7~8% 이내)과
오닐의 8% 손절 룰을 가이드라인으로 사용한다.
"""

from __future__ import annotations

from typing import Optional


def build_decision(
    quantity: float,
    buy_price: float,
    current_price: float,
    minervini: dict,
    canslim: dict,
    metrics: Optional[dict] = None,
    extra_request: str = "",
) -> dict:
    """포지션 의사결정 가이드 생성.

    Args:
        quantity: 보유 수량
        buy_price: 평균 매수가
        current_price: 현재가
        minervini: evaluate_minervini() 결과
        canslim: evaluate_canslim() 결과
        metrics: minervini['metrics'] 등 보조 지표
    """
    pnl_pct = (current_price / buy_price - 1) * 100 if buy_price > 0 else 0.0
    pnl_amount = (current_price - buy_price) * quantity
    cost = buy_price * quantity
    market_value = current_price * quantity

    # 손절가: 오닐 8% 룰 + 미너비니 50일선 이탈 중 더 보수적인 값
    stop_8pct = buy_price * 0.92
    ma50 = (metrics or {}).get("ma50")
    stop_ma50 = ma50 * 0.98 if ma50 else None

    candidate_stops = [stop_8pct]
    if stop_ma50:
        candidate_stops.append(stop_ma50)
    suggested_stop = max(candidate_stops)  # 더 높은(=덜 손실 보는) 손절

    # 목표가 (R-배수): 2R, 3R 기준 (오닐: 20-25% 익절 + 8% 손절 = 약 2.5~3R)
    risk_per_share = buy_price - suggested_stop
    targets = {}
    if risk_per_share > 0:
        targets["2R"] = buy_price + risk_per_share * 2
        targets["3R"] = buy_price + risk_per_share * 3
        # 오닐 권장 익절: 20-25%
        targets["오닐 20%"] = buy_price * 1.20
        targets["오닐 25%"] = buy_price * 1.25

    # 신호 종합
    minervini_ratio = (
        minervini.get("pass_count", 0) / minervini.get("total", 1)
        if minervini.get("valid")
        else 0
    )
    canslim_decided = canslim.get("decided_total", 0) or 1
    canslim_ratio = canslim.get("pass_count", 0) / canslim_decided

    signals = []

    # 손절 트리거
    if current_price <= suggested_stop:
        signals.append(
            (
                "URGENT",
                f"❗ 현재가 {current_price:,.0f} 가 제안 손절가 {suggested_stop:,.0f} "
                f"이하입니다. 손실 확대 방지를 위해 매도를 우선 검토하세요.",
            )
        )
    elif pnl_pct <= -7:
        signals.append(
            (
                "URGENT",
                f"❗ 손실률 {pnl_pct:.2f}% — 오닐/미너비니 모두 -7~8%를 절대 손절선으로 권합니다.",
            )
        )

    # Stage / 추세 신호
    stage = minervini.get("stage", "")
    if "Stage 4" in stage:
        signals.append(
            ("WARN", f"⚠️ 미너비니 Stage 4(하락) 추정 — 보유 비중 축소 검토.")
        )
    elif "Stage 3" in stage:
        signals.append(
            ("WARN", f"⚠️ 미너비니 Stage 3(분배/전환) 추정 — 신규 매수 자제, 트레일링 스탑 권장.")
        )
    elif "Stage 2" in stage and minervini_ratio >= 0.85:
        signals.append(
            ("GOOD", "🟢 Stage 2 강세 + 미너비니 기준 대부분 충족 - 추세 추종 보유 / 분할 추가매수 가능."),
        )

    # 미너비니 핵심 추세 무너짐
    m_metrics = minervini.get("metrics") or {}
    if m_metrics and current_price < (m_metrics.get("ma200") or 0):
        signals.append(("WARN", "⚠️ 현재가가 200일선 아래입니다 - 장기 추세 훼손."))
    if m_metrics and current_price < (m_metrics.get("ma50") or 0):
        signals.append(("INFO", "ℹ️ 50일선 이탈 - 단기 모멘텀 둔화. 거래량 동반 시 매도 신호."))

    # 오닐 시장 방향(M) 미통과 시 비중 축소
    m_crit = next((c for c in canslim.get("criteria", []) if c["id"] == "M"), None)
    if m_crit and m_crit.get("pass") is False:
        signals.append(("WARN", "⚠️ KOSPI 추세 약함 (M 미통과) - 신규 진입 비중 축소 및 현금 비중 확대."))

    # 익절/트레일링
    if pnl_pct >= 20:
        signals.append(
            ("INFO", f"💰 수익률 {pnl_pct:.1f}% — 오닐 20-25% 익절 룰 구간. 일부 차익 실현 또는 50일선 트레일링 스탑 검토.")
        )
    if pnl_pct >= 25:
        signals.append(
            ("INFO", f"💰 수익률 {pnl_pct:.1f}% — 적극적 차익 실현 검토. 단, 강력한 종목은 보유 유지 가능.")
        )

    # 종합 액션 추천
    action = _recommend_action(
        pnl_pct=pnl_pct,
        suggested_stop=suggested_stop,
        current_price=current_price,
        minervini_ratio=minervini_ratio,
        canslim_ratio=canslim_ratio,
        stage=stage,
        signals=signals,
    )

    return {
        "pnl_pct": pnl_pct,
        "pnl_amount": pnl_amount,
        "cost": cost,
        "market_value": market_value,
        "suggested_stop": suggested_stop,
        "stop_8pct": stop_8pct,
        "stop_ma50": stop_ma50,
        "targets": targets,
        "signals": signals,
        "action": action,
        "extra_request": extra_request,
    }


def _recommend_action(
    pnl_pct: float,
    suggested_stop: float,
    current_price: float,
    minervini_ratio: float,
    canslim_ratio: float,
    stage: str,
    signals: list,
) -> str:
    # 즉시 손절 시그널
    urgent = any(s[0] == "URGENT" for s in signals)
    if urgent or current_price <= suggested_stop or pnl_pct <= -8:
        return "🚨 매도(손절) — 손실 확대 방지를 위해 즉시 매도 우선 검토"

    if "Stage 4" in stage:
        return "🔴 매도(비중 축소) — 추세 훼손 상태, 반등 시 비중 축소"

    if pnl_pct >= 20 and minervini_ratio < 0.6:
        return "🟡 부분 익절 — 기준 약화 + 충분한 이익, 절반 매도 후 트레일링 스탑"

    if pnl_pct >= 25:
        return "🟢 트레일링 스탑으로 보유 / 부분 익절 — 50일선 이탈 시 정리"

    if minervini_ratio >= 0.85 and canslim_ratio >= 0.7 and "Stage 2" in stage:
        return "🟢 보유 / 추가매수 가능 — 추세·펀더 모두 양호"

    if minervini_ratio >= 0.6 and canslim_ratio >= 0.5:
        return "🟡 보유 — 추가 매수는 추세 확인 후"

    if pnl_pct < 0:
        return "🟡 손절선 모니터링 — 손실 확대 시 즉시 정리"

    return "⚪ 관망 — 기준 충족도 보통, 신규 진입 자제"
