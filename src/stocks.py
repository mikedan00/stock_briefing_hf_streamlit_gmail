\
from __future__ import annotations

import datetime as dt
import pandas as pd
import numpy as np
import yfinance as yf
from pykrx import stock

from .utils import today_kst, yyyymmdd, is_korean_text, pct, clamp

def build_krx_name_map() -> dict[str, str]:
    result = {}
    today = yyyymmdd(today_kst())
    for market in ["KOSPI", "KOSDAQ", "KONEX"]:
        try:
            tickers = stock.get_market_ticker_list(today, market=market)
            for t in tickers:
                name = stock.get_market_ticker_name(t)
                if name:
                    result[name.replace(" ", "").lower()] = t
        except Exception:
            continue
    return result

def resolve_symbol(token: str, krx_name_map: dict[str, str]) -> dict:
    raw = token.strip()
    compact = raw.replace(" ", "").lower()

    if raw.isdigit() and len(raw) == 6:
        try:
            name = stock.get_market_ticker_name(raw)
        except Exception:
            name = raw
        return {"input": raw, "ticker": raw, "name": name or raw, "market": "KR"}

    if is_korean_text(raw):
        ticker = krx_name_map.get(compact)
        if ticker:
            name = stock.get_market_ticker_name(ticker)
            return {"input": raw, "ticker": ticker, "name": name or raw, "market": "KR"}
        return {"input": raw, "ticker": raw, "name": raw, "market": "UNKNOWN"}

    return {"input": raw, "ticker": raw.upper(), "name": raw.upper(), "market": "GLOBAL"}

def get_kr_latest_price(ticker: str, lookback_days: int = 21) -> dict:
    end = today_kst()
    start = end - dt.timedelta(days=lookback_days)
    df = stock.get_market_ohlcv_by_date(yyyymmdd(start), yyyymmdd(end), ticker)

    if df is None or df.empty:
        raise ValueError(f"국내 가격 데이터 없음: {ticker}")

    df = df.dropna()
    last_date = df.index[-1]
    row = df.iloc[-1]

    prev_close = None
    if len(df) >= 2:
        prev_close = float(df.iloc[-2]["종가"])

    close = float(row["종가"])
    change_pct = pct(close, prev_close) if prev_close else None

    return {
        "ticker": ticker,
        "date": pd.to_datetime(last_date).date().isoformat(),
        "close": close,
        "previous_close": prev_close,
        "change_pct": change_pct,
        "open": float(row["시가"]),
        "high": float(row["고가"]),
        "low": float(row["저가"]),
        "volume": int(row["거래량"]),
        "source": "pykrx",
    }

def get_global_latest_price(ticker: str, lookback_days: int = 21) -> dict:
    t = yf.Ticker(ticker)
    hist = t.history(period=f"{lookback_days}d", interval="1d", auto_adjust=False)
    if hist is None or hist.empty:
        raise ValueError(f"해외 가격 데이터 없음: {ticker}")

    hist = hist.dropna(subset=["Close"])
    row = hist.iloc[-1]
    last_date = pd.to_datetime(hist.index[-1]).date().isoformat()

    prev_close = None
    if len(hist) >= 2:
        prev_close = float(hist.iloc[-2]["Close"])
    close = float(row["Close"])
    change_pct = pct(close, prev_close) if prev_close else None

    return {
        "ticker": ticker,
        "date": last_date,
        "close": close,
        "previous_close": prev_close,
        "change_pct": change_pct,
        "open": float(row["Open"]),
        "high": float(row["High"]),
        "low": float(row["Low"]),
        "volume": int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
        "source": "yfinance",
    }

def get_latest_price(info: dict) -> dict:
    if info["market"] == "KR":
        return get_kr_latest_price(info["ticker"])
    return get_global_latest_price(info["ticker"])

def get_kr_history(ticker: str, months: int = 7) -> pd.DataFrame:
    end = today_kst()
    start = end - dt.timedelta(days=months * 31)
    df = stock.get_market_ohlcv_by_date(yyyymmdd(start), yyyymmdd(end), ticker)
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.rename(columns={
        "시가": "Open",
        "고가": "High",
        "저가": "Low",
        "종가": "Close",
        "거래량": "Volume",
    })
    df.index = pd.to_datetime(df.index)
    return df[["Open", "High", "Low", "Close", "Volume"]].copy()

def get_global_history(ticker: str, months: int = 7) -> pd.DataFrame:
    hist = yf.Ticker(ticker).history(period=f"{months * 31}d", interval="1d", auto_adjust=False)
    if hist is None or hist.empty:
        return pd.DataFrame()
    hist.index = pd.to_datetime(hist.index)
    return hist[["Open", "High", "Low", "Close", "Volume"]].copy()

def compute_trend_metrics(hist: pd.DataFrame) -> dict:
    if hist is None or hist.empty or "Close" not in hist:
        return {}

    h = hist.dropna(subset=["Close"]).copy()
    close = h["Close"]
    last = float(close.iloc[-1])

    def ret_from_n(n: int):
        if len(close) <= n:
            return None
        return pct(last, float(close.iloc[-n-1]))

    daily_ret = close.pct_change().dropna()
    vol20 = float(daily_ret.tail(20).std() * np.sqrt(252) * 100) if len(daily_ret) >= 5 else None

    ma5 = float(close.tail(5).mean()) if len(close) >= 5 else None
    ma20 = float(close.tail(20).mean()) if len(close) >= 20 else None
    ma60 = float(close.tail(60).mean()) if len(close) >= 60 else None

    week_ret = ret_from_n(5)
    month_ret = ret_from_n(21)
    sixm_ret = ret_from_n(126)

    score = 0.0
    for r, w in [(week_ret, 0.34), (month_ret, 0.25), (sixm_ret, 0.15)]:
        if r is not None:
            score += clamp(r / 10, -1, 1) * w
    if ma5 and ma20:
        score += 0.15 if ma5 > ma20 else -0.15
    if ma20 and ma60:
        score += 0.11 if ma20 > ma60 else -0.11

    expected_pct = clamp(score * 2.2, -4.5, 4.5)
    if abs(expected_pct) < 0.25:
        direction = "NEUTRAL"
    else:
        direction = "UP" if expected_pct > 0 else "DOWN"

    return {
        "last_close": last,
        "week_return_pct": week_ret,
        "month_return_pct": month_ret,
        "six_month_return_pct": sixm_ret,
        "volatility_20d_annualized_pct": vol20,
        "ma5": ma5,
        "ma20": ma20,
        "ma60": ma60,
        "heuristic_direction": direction,
        "heuristic_expected_change_pct": round(expected_pct, 2),
    }

def get_kr_investor_flow(ticker: str, lookback_days: int = 30) -> dict:
    end = today_kst()
    start = end - dt.timedelta(days=lookback_days * 2)

    try:
        df = stock.get_market_trading_value_by_date(yyyymmdd(start), yyyymmdd(end), ticker)
        if df is None or df.empty:
            return {}
        tail = df.tail(lookback_days)
        sums = tail.sum(numeric_only=True).to_dict()

        result = {
            "period_start": pd.to_datetime(tail.index[0]).date().isoformat(),
            "period_end": pd.to_datetime(tail.index[-1]).date().isoformat(),
            "unit": "KRW trading value net buy/sell",
        }
        for key in ["개인", "기관합계", "외국인합계", "기타법인"]:
            if key in sums:
                result[key] = int(sums[key])
        return result
    except Exception as e:
        return {"error": str(e)}

def get_history_and_metrics(info: dict) -> tuple[pd.DataFrame, dict, dict]:
    if info["market"] == "KR":
        hist = get_kr_history(info["ticker"])
        flows = get_kr_investor_flow(info["ticker"])
    else:
        hist = get_global_history(info["ticker"])
        flows = {}
    return hist, compute_trend_metrics(hist), flows
