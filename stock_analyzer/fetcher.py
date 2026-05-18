"""네이버 금융에서 코스피/코스닥 종목 데이터를 수집한다.

가격 시계열: fchart.stock.naver.com (XML)
종목 요약/펀더멘털: finance.naver.com/item/main.naver (HTML)
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": "https://finance.naver.com/",
}

FCHART_URL = "https://fchart.stock.naver.com/sise.nhn"
MAIN_URL = "https://finance.naver.com/item/main.naver"

KOSPI_SYMBOL = "KOSPI"


@dataclass
class StockSummary:
    code: str
    name: str = ""
    market: str = ""
    current_price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[float] = None
    market_cap_eok: Optional[float] = None
    shares_outstanding: Optional[float] = None
    foreign_ratio: Optional[float] = None
    per: Optional[float] = None
    eps: Optional[float] = None
    pbr: Optional[float] = None
    roe: Optional[float] = None
    dividend_yield: Optional[float] = None
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    fundamentals: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "종목코드": self.code,
            "종목명": self.name,
            "시장": self.market,
            "현재가": self.current_price,
            "전일대비": self.change,
            "등락률(%)": self.change_pct,
            "거래량": self.volume,
            "시가총액(억)": self.market_cap_eok,
            "상장주식수": self.shares_outstanding,
            "외국인소진율(%)": self.foreign_ratio,
            "PER": self.per,
            "EPS": self.eps,
            "PBR": self.pbr,
            "ROE(%)": self.roe,
            "배당수익률(%)": self.dividend_yield,
            "52주최고": self.high_52w,
            "52주최저": self.low_52w,
        }


def _to_float(text: str) -> Optional[float]:
    if text is None:
        return None
    cleaned = re.sub(r"[,\s%원배]", "", str(text))
    cleaned = cleaned.replace("\xa0", "")
    if cleaned in {"", "-", "N/A"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


class NaverFetcher:
    def __init__(self, session: Optional[requests.Session] = None, timeout: int = 10):
        self.session = session or requests.Session()
        self.session.headers.update(HEADERS)
        self.timeout = timeout

    def get_price_history(self, code: str, count: int = 400) -> pd.DataFrame:
        """일봉 OHLCV 데이터를 가져온다."""
        params = {
            "symbol": code,
            "timeframe": "day",
            "count": count,
            "requestType": 0,
        }
        for attempt in range(3):
            try:
                r = self.session.get(FCHART_URL, params=params, timeout=self.timeout)
                r.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(1 + attempt)

        try:
            root = ET.fromstring(r.text)
        except ET.ParseError as e:
            raise RuntimeError(f"네이버 차트 응답 파싱 실패: {e}")

        rows = []
        for item in root.iter("item"):
            data = item.get("data")
            if not data:
                continue
            parts = data.split("|")
            if len(parts) < 6:
                continue
            try:
                rows.append(
                    {
                        "date": pd.to_datetime(parts[0]),
                        "open": float(parts[1]),
                        "high": float(parts[2]),
                        "low": float(parts[3]),
                        "close": float(parts[4]),
                        "volume": float(parts[5]),
                    }
                )
            except (ValueError, TypeError):
                continue

        if not rows:
            raise RuntimeError(
                f"[{code}] 가격 데이터를 가져오지 못했습니다. 종목코드를 확인하세요."
            )
        df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
        return df

    def get_kospi_history(self, count: int = 400) -> pd.DataFrame:
        return self.get_price_history(KOSPI_SYMBOL, count=count)

    def get_summary(self, code: str) -> StockSummary:
        """종목 메인 페이지에서 요약 정보를 가져온다."""
        params = {"code": code}
        r = self.session.get(MAIN_URL, params=params, timeout=self.timeout)
        r.raise_for_status()
        r.encoding = "euc-kr"
        soup = BeautifulSoup(r.text, "lxml")

        summary = StockSummary(code=code)

        name_el = soup.select_one("div.wrap_company h2 a")
        if name_el:
            summary.name = name_el.get_text(strip=True)

        desc = soup.select_one("div.description")
        if desc:
            text = desc.get_text(" ", strip=True)
            if "코스피" in text or "KOSPI" in text.upper():
                summary.market = "KOSPI"
            elif "코스닥" in text or "KOSDAQ" in text.upper():
                summary.market = "KOSDAQ"
            img = desc.select_one("img")
            if img and not summary.market:
                alt = img.get("alt", "")
                if "코스피" in alt:
                    summary.market = "KOSPI"
                elif "코스닥" in alt:
                    summary.market = "KOSDAQ"

        today_blind = soup.select_one("p.no_today span.blind")
        if today_blind:
            summary.current_price = _to_float(today_blind.get_text())

        exday = soup.select_one("p.no_exday")
        if exday:
            blinds = exday.select("span.blind")
            if len(blinds) >= 2:
                summary.change = _to_float(blinds[0].get_text())
                summary.change_pct = _to_float(blinds[1].get_text())
                ico = exday.select_one("em")
                if ico and ("down" in (ico.get("class") or []) or "하락" in ico.get_text()):
                    if summary.change is not None:
                        summary.change = -abs(summary.change)
                    if summary.change_pct is not None:
                        summary.change_pct = -abs(summary.change_pct)

        # 시가총액/상장주식수/외국인소진율 등 (왼쪽 요약 테이블)
        info_table = soup.select_one("div.first table.lwidth, table.lwidth")
        if info_table is None:
            info_table = soup.select_one("table[summary*='종목별 시세']")
        for row in soup.select("table.lwidth tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if not th or not td:
                continue
            key = th.get_text(" ", strip=True)
            val_text = td.get_text(" ", strip=True)
            summary.fundamentals[key] = val_text

            if "시가총액" in key and summary.market_cap_eok is None:
                m = re.search(r"([\d,]+)\s*억", val_text)
                if m:
                    summary.market_cap_eok = _to_float(m.group(1))
            if "상장주식수" in key:
                summary.shares_outstanding = _to_float(re.split(r"\s", val_text)[0])
            if "외국인소진율" in key or "외국인비율" in key:
                summary.foreign_ratio = _to_float(val_text)
            if "52주최고" in key or "52주 최고" in key:
                parts = re.findall(r"[\d,]+", val_text)
                if len(parts) >= 1:
                    summary.high_52w = _to_float(parts[0])
                if len(parts) >= 2:
                    summary.low_52w = _to_float(parts[1])
            if "거래량" in key and "전일" not in key:
                summary.volume = _to_float(val_text)

        # PER/EPS/PBR/ROE/배당수익률 등 (per_table 영역)
        per_table = soup.select_one("table.per_table")
        if per_table:
            for row in per_table.select("tr"):
                th = row.select_one("th")
                if not th:
                    continue
                key = th.get_text(" ", strip=True)
                em_vals = [em.get_text(" ", strip=True) for em in row.select("em")]
                td = row.select_one("td")
                val_text = td.get_text(" ", strip=True) if td else ""
                summary.fundamentals[key] = val_text

                first_num = None
                for v in em_vals:
                    fv = _to_float(v)
                    if fv is not None:
                        first_num = fv
                        break

                if "PER" in key and "EPS" in key:
                    nums = re.findall(r"-?[\d,\.]+", val_text)
                    if len(nums) >= 1:
                        summary.per = _to_float(nums[0])
                    if len(nums) >= 2:
                        summary.eps = _to_float(nums[1])
                elif "PBR" in key and "BPS" in key:
                    nums = re.findall(r"-?[\d,\.]+", val_text)
                    if nums:
                        summary.pbr = _to_float(nums[0])
                elif "배당수익률" in key:
                    summary.dividend_yield = first_num
                elif key.strip() == "ROE":
                    summary.roe = first_num

        return summary


def relative_strength(stock_df: pd.DataFrame, bench_df: pd.DataFrame, lookback: int = 252) -> Optional[float]:
    """간이 상대강도(RS) 점수: 종목 수익률 - 벤치마크 수익률 (lookback일).
    값이 클수록 시장 대비 강세.
    """
    if len(stock_df) < lookback or len(bench_df) < lookback:
        lookback = min(len(stock_df), len(bench_df)) - 1
        if lookback < 20:
            return None
    s = stock_df["close"].iloc[-1] / stock_df["close"].iloc[-lookback - 1] - 1
    b = bench_df["close"].iloc[-1] / bench_df["close"].iloc[-lookback - 1] - 1
    return (s - b) * 100


def weighted_rs_score(stock_df: pd.DataFrame, bench_df: pd.DataFrame) -> dict:
    """오닐이 사용하는 가중 RS 근사: 3/6/9/12개월 가중 평균 수익률.
    가중치: 1Q=2, 2Q=1, 3Q=1, 4Q=1 (3개월 최근 가중치).
    """
    res = {"periods": {}, "weighted": None, "vs_bench": None}
    periods = {"3M": 63, "6M": 126, "9M": 189, "12M": 252}
    weights = {"3M": 0.4, "6M": 0.2, "9M": 0.2, "12M": 0.2}

    if len(stock_df) < 21 or len(bench_df) < 21:
        return res

    stock_close = stock_df["close"]
    bench_close = bench_df["close"]
    weighted_stock = 0.0
    weighted_bench = 0.0
    total_weight = 0.0
    for label, days in periods.items():
        if len(stock_close) <= days or len(bench_close) <= days:
            continue
        s_ret = stock_close.iloc[-1] / stock_close.iloc[-days - 1] - 1
        b_ret = bench_close.iloc[-1] / bench_close.iloc[-days - 1] - 1
        res["periods"][label] = {"stock": s_ret * 100, "bench": b_ret * 100}
        w = weights[label]
        weighted_stock += s_ret * w
        weighted_bench += b_ret * w
        total_weight += w

    if total_weight > 0:
        res["weighted"] = weighted_stock / total_weight * 100
        res["vs_bench"] = (weighted_stock - weighted_bench) / total_weight * 100
    return res
