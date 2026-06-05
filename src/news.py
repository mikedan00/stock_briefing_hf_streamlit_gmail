\
from __future__ import annotations

import datetime as dt
import urllib.parse
import requests
import feedparser
from bs4 import BeautifulSoup
import yfinance as yf
from email.utils import parsedate_to_datetime

from .utils import today_kst, KST

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; StockBriefingBot/1.0)"
}

def _parse_date(value):
    if not value:
        return None
    try:
        d = parsedate_to_datetime(value)
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d.astimezone(KST)
    except Exception:
        return None

def _is_today_kst(dt_obj):
    if not dt_obj:
        return False
    return dt_obj.astimezone(KST).date() == today_kst()

def google_news(query: str, lang: str = "ko", max_items: int = 10) -> list[dict]:
    if lang == "ko":
        params = {
            "q": f'{query} when:1d',
            "hl": "ko",
            "gl": "KR",
            "ceid": "KR:ko",
        }
    else:
        params = {
            "q": f'{query} stock OR shares when:1d',
            "hl": "en-US",
            "gl": "US",
            "ceid": "US:en",
        }
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(params)
    feed = feedparser.parse(url)
    items = []
    fallback = []

    for e in feed.entries:
        pub_dt = _parse_date(getattr(e, "published", ""))
        item = {
            "title": BeautifulSoup(getattr(e, "title", ""), "html.parser").get_text(" ", strip=True),
            "link": getattr(e, "link", ""),
            "published": pub_dt.isoformat() if pub_dt else "",
            "source": "Google News",
            "summary": BeautifulSoup(getattr(e, "summary", ""), "html.parser").get_text(" ", strip=True),
            "lang": lang,
        }
        fallback.append(item)
        if _is_today_kst(pub_dt):
            items.append(item)

    return (items or fallback)[:max_items]

def naver_news(query: str, max_items: int = 10) -> list[dict]:
    url = "https://search.naver.com/search.naver?" + urllib.parse.urlencode({
        "where": "news",
        "query": query,
        "sort": "1",
    })
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        items = []
        for box in soup.select("div.news_area")[:max_items * 2]:
            a = box.select_one("a.news_tit")
            if not a:
                continue
            title = a.get("title") or a.get_text(" ", strip=True)
            link = a.get("href", "")
            desc = ""
            desc_el = box.select_one(".news_dsc")
            if desc_el:
                desc = desc_el.get_text(" ", strip=True)
            date_text = ""
            info_group = box.select(".info_group span.info")
            if info_group:
                date_text = info_group[-1].get_text(" ", strip=True)

            items.append({
                "title": title,
                "link": link,
                "published": date_text,
                "source": "Naver News",
                "summary": desc,
                "lang": "ko",
            })

        return items[:max_items]
    except Exception as e:
        return [{
            "title": "Naver News 수집 실패",
            "summary": str(e),
            "source": "Naver News",
            "link": "",
            "published": "",
            "lang": "ko",
        }]

def yahoo_finance_news(ticker: str, max_items: int = 10) -> list[dict]:
    try:
        news = yf.Ticker(ticker).news or []
    except Exception as e:
        return [{
            "title": "Yahoo/yfinance 뉴스 수집 실패",
            "summary": str(e),
            "source": "Yahoo Finance",
            "link": "",
            "published": "",
            "lang": "en",
        }]

    items = []
    fallback = []

    for n in news:
        content = n.get("content", n)
        title = content.get("title") or n.get("title") or ""
        summary = content.get("summary") or n.get("summary") or ""

        link = ""
        if isinstance(content.get("canonicalUrl"), dict):
            link = content.get("canonicalUrl", {}).get("url", "")
        link = link or n.get("link", "")

        pub_ts = content.get("pubDate") or n.get("providerPublishTime")
        pub_dt = None

        if isinstance(pub_ts, int):
            pub_dt = dt.datetime.fromtimestamp(pub_ts, tz=dt.timezone.utc).astimezone(KST)
        elif isinstance(pub_ts, str):
            try:
                pub_dt = dt.datetime.fromisoformat(pub_ts.replace("Z", "+00:00")).astimezone(KST)
            except Exception:
                pub_dt = _parse_date(pub_ts)

        item = {
            "title": title,
            "link": link,
            "published": pub_dt.isoformat() if pub_dt else "",
            "source": "Yahoo Finance",
            "summary": summary,
            "lang": "en",
        }
        fallback.append(item)
        if _is_today_kst(pub_dt):
            items.append(item)

    return (items or fallback)[:max_items]

def collect_news_for_stock(name: str, ticker: str, market: str, max_each: int = 10) -> dict:
    ko_query = f"{name} {ticker} 주식"
    en_query = f"{name} {ticker}"

    domestic = []
    domestic.extend(google_news(ko_query, lang="ko", max_items=max_each))
    domestic.extend(naver_news(ko_query, max_items=max_each))

    seen = set()
    domestic_unique = []
    for x in domestic:
        key = (x.get("title", ""), x.get("link", ""))
        if key not in seen:
            domestic_unique.append(x)
            seen.add(key)
        if len(domestic_unique) >= max_each:
            break

    overseas = []
    overseas.extend(google_news(en_query, lang="en", max_items=max_each))
    if market != "KR":
        overseas.extend(yahoo_finance_news(ticker, max_items=max_each))

    seen = set()
    overseas_unique = []
    for x in overseas:
        key = (x.get("title", ""), x.get("link", ""))
        if key not in seen:
            overseas_unique.append(x)
            seen.add(key)
        if len(overseas_unique) >= max_each:
            break

    return {"domestic": domestic_unique, "overseas": overseas_unique}
