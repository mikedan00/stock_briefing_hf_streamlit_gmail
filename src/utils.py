\
from __future__ import annotations

import datetime as dt
import re
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

def today_kst() -> dt.date:
    return dt.datetime.now(KST).date()

def now_kst_str() -> str:
    return dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")

def yyyymmdd(d: dt.date) -> str:
    return d.strftime("%Y%m%d")

def clean_tokens(raw: str) -> list[str]:
    parts = re.split(r"[,;\n\t]+", raw.strip())
    result = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # 공백으로만 구분된 티커도 일부 허용하되, 한국 종목명 공백은 보존하기 위해 보수적으로 처리
        if "," not in raw and "\n" not in raw and ";" not in raw and "\t" not in raw:
            result.extend([x.strip() for x in p.split(" ") if x.strip()])
        else:
            result.append(p)
    return result

def is_korean_text(s: str) -> bool:
    return bool(re.search(r"[가-힣]", s))

def safe_float(x, default=0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default

def pct(a, b):
    try:
        if b == 0 or b is None:
            return None
        return (a / b - 1) * 100
    except Exception:
        return None

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def fmt_pct(v):
    if v is None:
        return "-"
    try:
        return f"{float(v):+.2f}%"
    except Exception:
        return "-"

def fmt_num(v):
    if v is None:
        return "-"
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return str(v)
