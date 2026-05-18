"""한국 코스피 종목 분석기 — 윌리엄 오닐 + 마크 미너비니 기준.

실행: `streamlit run app.py`
"""

from __future__ import annotations

import time
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from stock_analyzer import (
    NaverFetcher,
    build_decision,
    evaluate_canslim,
    evaluate_minervini,
)
from stock_analyzer.fetcher import weighted_rs_score


st.set_page_config(
    page_title="한국 주식 분석기 — O'Neil & Minervini",
    page_icon="📈",
    layout="wide",
)


@st.cache_resource
def get_fetcher() -> NaverFetcher:
    return NaverFetcher()


@st.cache_data(ttl=300)
def fetch_data(code: str):
    f = get_fetcher()
    price = f.get_price_history(code, count=400)
    summary = f.get_summary(code)
    kospi = f.get_kospi_history(count=400)
    return price, summary.as_dict(), summary.fundamentals, kospi


def render_price_chart(price_df: pd.DataFrame, name: str):
    df = price_df.tail(260).copy()
    df["ma50"] = price_df["close"].rolling(50).mean().tail(260).values
    df["ma150"] = price_df["close"].rolling(150).mean().tail(260).values
    df["ma200"] = price_df["close"].rolling(200).mean().tail(260).values

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.75, 0.25],
        subplot_titles=("가격 / 이동평균선", "거래량"),
    )
    fig.add_trace(
        go.Candlestick(
            x=df["date"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name=name,
            increasing_line_color="#d62728",
            decreasing_line_color="#1f77b4",
        ),
        row=1,
        col=1,
    )
    for col, color in [
        ("ma50", "#ff7f0e"),
        ("ma150", "#2ca02c"),
        ("ma200", "#9467bd"),
    ]:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df[col],
                mode="lines",
                name=col.upper(),
                line=dict(width=1.4, color=color),
            ),
            row=1,
            col=1,
        )
    fig.add_trace(
        go.Bar(
            x=df["date"],
            y=df["volume"],
            name="거래량",
            marker_color="#888",
            opacity=0.6,
        ),
        row=2,
        col=1,
    )
    fig.update_layout(
        height=620,
        margin=dict(t=50, b=10, l=10, r=10),
        showlegend=True,
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    return fig


def render_criteria_table(criteria: list[dict]):
    rows = []
    for c in criteria:
        passed = c.get("pass")
        if passed is True:
            mark = "✅"
        elif passed is False:
            mark = "❌"
        else:
            mark = "❓"
        rows.append({"": mark, "기준": c.get("name", ""), "세부": c.get("detail", "")})
    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, use_container_width=True)


def render_signals(signals: list[tuple[str, str]]):
    if not signals:
        st.info("특이 신호 없음.")
        return
    for level, msg in signals:
        if level == "URGENT":
            st.error(msg)
        elif level == "WARN":
            st.warning(msg)
        elif level == "GOOD":
            st.success(msg)
        else:
            st.info(msg)


# =============================================================
# UI
# =============================================================
st.title("📈 한국 주식 분석기 — O'Neil(CAN SLIM) + Minervini Trend Template")
st.caption(
    f"실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
    "데이터: 네이버 금융 (5분 캐시)"
)

with st.sidebar:
    st.header("🔍 종목 입력")
    code_input = st.text_input(
        "종목 코드 (6자리)",
        value="005930",
        help="예: 005930 (삼성전자), 000660 (SK하이닉스), 005380 (현대차)",
    )
    code = code_input.strip().zfill(6) if code_input.strip().isdigit() else code_input.strip()

    if st.button("🔄 강제 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.header("💼 보유 정보")
    holding_quantity = st.number_input("보유 수량", min_value=0.0, value=0.0, step=1.0)
    buy_price = st.number_input("평균 매수가 (원)", min_value=0.0, value=0.0, step=100.0)

    st.markdown("---")
    st.header("📊 펀더멘털 보강 (선택)")
    st.caption(
        "오닐 C/A/I는 가격 데이터만으로 완벽히 평가하기 어려워 "
        "직접 입력하면 더 정확하게 평가됩니다."
    )
    q_eps_input = st.text_input("분기 EPS YoY 성장률 (%)", value="", placeholder="예: 35.5")
    a_eps_input = st.text_input("연간 EPS 3년 평균 성장률 (%)", value="", placeholder="예: 28")
    inst_input = st.text_input("기관 보유율 (%)", value="", placeholder="예: 25.3")

    st.markdown("---")
    extra_request = st.text_area(
        "📝 추가 요청 / 메모",
        value="",
        placeholder=(
            "예) 특정 산업 비교, 최근 공시 반영, "
            "지지/저항 라인 추정, 분할매수 전략 추천 등"
        ),
        height=120,
    )

    analyze = st.button("📡 분석 실행", type="primary", use_container_width=True)


def _parse_pct(text: str):
    if not text.strip():
        return None
    try:
        return float(text.replace(",", "").replace("%", "").strip())
    except ValueError:
        return None


user_fundamentals = {
    "q_eps_growth": _parse_pct(q_eps_input),
    "a_eps_growth": _parse_pct(a_eps_input),
    "institutional_ratio": _parse_pct(inst_input),
}

if not analyze and "last_code" not in st.session_state:
    st.info(
        "👈 왼쪽 사이드바에 **종목 코드**(6자리)를 입력하고 **분석 실행**을 눌러주세요.\n\n"
        "참고:\n"
        "- 코스피 종목 위주로 평가하도록 설계되었습니다.\n"
        "- 가격 데이터: 네이버 금융 fchart\n"
        "- 펀더멘털 일부는 네이버 메인 페이지에서 자동 수집, 부족한 항목은 직접 입력."
    )
    st.stop()

if analyze:
    st.session_state["last_code"] = code

code = st.session_state.get("last_code", code)

# ---- 데이터 수집 ----
try:
    with st.spinner(f"[{code}] 네이버 금융에서 데이터 수집 중..."):
        price_df, summary_dict, fundamentals, kospi_df = fetch_data(code)
except Exception as e:
    st.error(f"데이터 수집 실패: {e}")
    st.stop()

market = summary_dict.get("시장", "")
if market and market != "KOSPI":
    st.warning(
        f"⚠️ 입력 종목은 **{market}** 상장 종목입니다. "
        f"이 도구는 **코스피** 종목 기준으로 설계되었으나 평가는 그대로 수행합니다."
    )

# ---- 상단 헤더 ----
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("종목명", summary_dict.get("종목명", "-"))
col2.metric("종목코드", summary_dict.get("종목코드", "-"))
cur = summary_dict.get("현재가")
chg_pct = summary_dict.get("등락률(%)")
col3.metric(
    "현재가",
    f"{cur:,.0f}원" if cur else "-",
    delta=f"{chg_pct:+.2f}%" if chg_pct is not None else None,
)
col4.metric("시장", summary_dict.get("시장", "-"))
mcap = summary_dict.get("시가총액(억)")
col5.metric("시가총액", f"{mcap:,.0f}억원" if mcap else "-")

st.markdown("---")

# ---- 차트 ----
st.subheader("📊 가격 차트 / 이동평균선")
fig = render_price_chart(price_df, summary_dict.get("종목명", code))
st.plotly_chart(fig, use_container_width=True)

# ---- 평가 ----
rs = weighted_rs_score(price_df, kospi_df)
rs_score = rs.get("vs_bench")

minervini = evaluate_minervini(price_df, rs_score=rs_score)
canslim = evaluate_canslim(
    price_df,
    kospi_df=kospi_df,
    summary=summary_dict,
    rs_score=rs_score,
    user_fundamentals=user_fundamentals,
)

left, right = st.columns(2)

with left:
    st.subheader("🎯 Mark Minervini Trend Template")
    if minervini.get("valid"):
        st.markdown(
            f"**통과: {minervini['pass_count']}/{minervini['total']}**  | "
            f"**Stage**: {minervini.get('stage', '-')}"
        )
        st.markdown(f"**판정**: {minervini.get('verdict', '-')}")
        render_criteria_table(minervini["criteria"])
        m = minervini["metrics"]
        st.caption(
            f"50MA {m['ma50']:,.0f} / 150MA {m['ma150']:,.0f} / 200MA {m['ma200']:,.0f} | "
            f"52W High {m['high_52w']:,.0f} / Low {m['low_52w']:,.0f} | "
            f"고점대비 {m['pct_from_high']:+.1f}% / 저점대비 +{m['pct_from_low']:.1f}%"
        )
    else:
        st.warning(minervini.get("error", "평가 불가"))

with right:
    st.subheader("💎 William O'Neil CAN SLIM")
    st.markdown(
        f"**통과: {canslim['pass_count']}/{canslim['decided_total']}** "
        f"(전체 {canslim['total']} 중 평가 가능 {canslim['decided_total']})"
    )
    st.markdown(f"**판정**: {canslim.get('verdict', '-')}")
    render_criteria_table(canslim["criteria"])
    if rs:
        periods = rs.get("periods", {})
        if periods:
            st.caption(
                "기간별 수익률 vs KOSPI: "
                + " / ".join(
                    f"{k} 종목 {v['stock']:+.1f}% vs KOSPI {v['bench']:+.1f}%"
                    for k, v in periods.items()
                )
            )

st.markdown("---")

# ---- 보유 정보 분석 ----
st.subheader("💼 보유 포지션 의사결정 보조")

if holding_quantity > 0 and buy_price > 0:
    current_price = float(price_df["close"].iloc[-1])
    decision = build_decision(
        quantity=holding_quantity,
        buy_price=buy_price,
        current_price=current_price,
        minervini=minervini,
        canslim=canslim,
        metrics=minervini.get("metrics"),
        extra_request=extra_request,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "평가 손익",
        f"{decision['pnl_amount']:+,.0f}원",
        delta=f"{decision['pnl_pct']:+.2f}%",
    )
    c2.metric("매입 원가", f"{decision['cost']:,.0f}원")
    c3.metric("현재 평가액", f"{decision['market_value']:,.0f}원")
    c4.metric("제안 손절가", f"{decision['suggested_stop']:,.0f}원")

    st.markdown(f"### 🎯 종합 액션: **{decision['action']}**")

    if decision["targets"]:
        cols = st.columns(len(decision["targets"]))
        for col, (label, price) in zip(cols, decision["targets"].items()):
            col.metric(f"목표가 ({label})", f"{price:,.0f}원")

    st.markdown("#### 🔔 신호")
    render_signals(decision["signals"])

    st.caption(
        f"손절 산출 — 매수가 -8% : {decision['stop_8pct']:,.0f}원"
        + (
            f", 50일선 -2% : {decision['stop_ma50']:,.0f}원 (둘 중 더 보수적인 값 채택)"
            if decision["stop_ma50"]
            else ""
        )
    )
else:
    st.info(
        "사이드바에 **보유 수량**과 **평균 매수가**를 입력하면 "
        "PnL · 손절가 · 목표가 · 액션 추천이 표시됩니다."
    )

# ---- 추가 요청 ----
if extra_request.strip():
    st.markdown("---")
    st.subheader("📝 추가 요청 메모")
    st.write(extra_request)
    st.caption(
        "위 메모는 의사결정 기록용입니다. "
        "산업/비교종목 분석 등 자동화가 필요하면 종목 코드를 추가로 입력해 좌측에서 비교 분석을 반복하세요."
    )

# ---- 원본 데이터 ----
with st.expander("🔍 수집된 원본 데이터 보기"):
    st.markdown("**종목 요약**")
    st.json({k: v for k, v in summary_dict.items() if v is not None})
    if fundamentals:
        st.markdown("**네이버 펀더멘털 (raw)**")
        st.json(fundamentals)
    st.markdown("**최근 30일 가격**")
    st.dataframe(price_df.tail(30).iloc[::-1], use_container_width=True, hide_index=True)

st.caption(
    "⚠️ 본 도구는 학습/연구 목적의 의사결정 보조 도구입니다. "
    "실제 매매 결과에 대한 책임은 사용자에게 있습니다."
)
