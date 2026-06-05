\
from __future__ import annotations

import json
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from src.config import MAX_TICKERS, HF_MODEL_ID, HF_ROUTER_URL, GMAIL_SENDER
from src.utils import clean_tokens, today_kst, now_kst_str, fmt_pct, fmt_num
from src.stocks import (
    build_krx_name_map,
    resolve_symbol,
    get_latest_price,
    get_history_and_metrics,
)
from src.news import collect_news_for_stock
from src.llm import translate_english_news_to_korean, make_final_briefing
from src.emailer import send_report_email, is_valid_email

st.set_page_config(
    page_title="AI 주식 브리핑: PyKRX + yfinance + HF Router + Gmail",
    layout="wide",
)

st.title("📈 AI 주식 브리핑 + Gmail 발송")
st.caption("PyKRX + yfinance + Google/Naver/Yahoo News + Hugging Face Router + Gmail SMTP")

with st.sidebar:
    st.header("설정")
    st.write(f"오늘 날짜(KST): **{today_kst().isoformat()}**")
    st.write(f"현재 시각: **{now_kst_str()}**")
    st.write(f"HF Router: `{HF_ROUTER_URL}`")
    st.write(f"HF Model: `{HF_MODEL_ID}`")
    if GMAIL_SENDER:
        st.success(f"Gmail Sender 설정됨: {GMAIL_SENDER}")
    else:
        st.warning("Gmail Sender 미설정")
    max_news = st.slider("국내/해외 뉴스 개수", 3, 10, 10)
    use_llm = st.checkbox("HF Router LLM 브리핑 생성", value=True)
    translate_en = st.checkbox("영어 뉴스 한국어 번역", value=True)

st.markdown("""
입력 예시: `삼성전자, SK하이닉스, 005930, 000660, AAPL, MSFT, NVDA`

- 국내 종목명 또는 6자리 종목코드 입력 가능
- 해외 종목은 Yahoo Finance 티커 입력
- 최대 10개 종목
""")

raw = st.text_area("분석할 종목 입력", value="삼성전자, SK하이닉스, AAPL, NVDA", height=90)

if "briefing_payload" not in st.session_state:
    st.session_state.briefing_payload = None
if "briefing_report" not in st.session_state:
    st.session_state.briefing_report = ""
if "chart_store" not in st.session_state:
    st.session_state.chart_store = {}

run = st.button("🚀 오늘 브리핑 생성", type="primary")

if run:
    tokens = clean_tokens(raw)[:MAX_TICKERS]
    if not tokens:
        st.error("분석할 종목을 1개 이상 입력하세요.")
        st.stop()

    with st.spinner("KRX 종목명 매핑을 불러오는 중..."):
        krx_name_map = build_krx_name_map()

    all_results = []
    chart_store = {}

    progress = st.progress(0)

    for idx, token in enumerate(tokens):
        with st.status(f"분석 중: {token}", expanded=False) as status:
            info = resolve_symbol(token, krx_name_map)

            result = {
                "input": token,
                "resolved": info,
                "price": {},
                "metrics": {},
                "flow": {},
                "news": {"domestic": [], "overseas": []},
                "errors": [],
            }

            try:
                status.write("가격 수집 중...")
                result["price"] = get_latest_price(info)
            except Exception as e:
                result["errors"].append(f"가격 수집 실패: {e}")

            try:
                status.write("주가 추이와 수급 분석 중...")
                hist, metrics, flows = get_history_and_metrics(info)
                result["metrics"] = metrics
                result["flow"] = flows
                if hist is not None and not hist.empty:
                    chart_store[info["ticker"]] = hist.reset_index().to_dict("records")
            except Exception as e:
                result["errors"].append(f"추세/수급 분석 실패: {e}")

            try:
                status.write("국내/해외 뉴스 수집 중...")
                news = collect_news_for_stock(info["name"], info["ticker"], info["market"], max_each=max_news)
                if translate_en:
                    news["overseas"] = translate_english_news_to_korean(news["overseas"], info["name"])
                result["news"] = news
            except Exception as e:
                result["errors"].append(f"뉴스 수집 실패: {e}")

            all_results.append(result)
            status.update(label=f"완료: {token}", state="complete")

        progress.progress((idx + 1) / len(tokens))

    payload = {
        "as_of_kst": now_kst_str(),
        "stocks": all_results,
    }

    st.session_state.briefing_payload = payload
    st.session_state.chart_store = chart_store

    if use_llm:
        with st.spinner("HF Router LLM으로 최종 투자 브리핑을 생성하는 중..."):
            st.session_state.briefing_report = make_final_briefing(payload)
    else:
        st.session_state.briefing_report = "LLM 브리핑 생성을 끈 상태입니다. 가격/뉴스/수급 데이터만 확인하세요."

    st.success("분석 완료")

if st.session_state.briefing_payload:
    payload = st.session_state.briefing_payload
    results = payload["stocks"]

    st.header("1. 최신 종가 요약")
    rows = []
    for r in results:
        info = r["resolved"]
        price = r.get("price", {})
        metrics = r.get("metrics", {})
        rows.append({
            "입력": r["input"],
            "종목명": info.get("name"),
            "티커": info.get("ticker"),
            "시장": info.get("market"),
            "기준일": price.get("date"),
            "종가": price.get("close"),
            "전일대비%": price.get("change_pct"),
            "거래량": price.get("volume"),
            "이번주%": metrics.get("week_return_pct"),
            "이번달%": metrics.get("month_return_pct"),
            "6개월%": metrics.get("six_month_return_pct"),
            "MA5": metrics.get("ma5"),
            "MA20": metrics.get("ma20"),
            "MA60": metrics.get("ma60"),
            "예상방향": metrics.get("heuristic_direction"),
            "예상등락률%": metrics.get("heuristic_expected_change_pct"),
        })

    df_summary = pd.DataFrame(rows)
    st.dataframe(df_summary, use_container_width=True)

    st.header("2. 주가 차트")
    chart_store = st.session_state.chart_store or {}
    for r in results:
        info = r["resolved"]
        ticker = info.get("ticker")
        name = info.get("name")
        rows_chart = chart_store.get(ticker, [])

        if rows_chart:
            hist = pd.DataFrame(rows_chart)
            if "index" in hist.columns:
                hist = hist.rename(columns={"index": "Date"})
            elif "날짜" in hist.columns:
                hist = hist.rename(columns={"날짜": "Date"})
            else:
                hist["Date"] = pd.RangeIndex(len(hist))

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=hist["Date"], y=hist["Close"], mode="lines", name="Close"))
            fig.update_layout(title=f"{name} ({ticker}) 최근 약 6개월 종가", height=360)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"{name} ({ticker}) 차트 데이터가 없습니다.")

    st.header("3. 수급 요약")
    flow_rows = []
    for r in results:
        info = r["resolved"]
        flow = r.get("flow", {})
        flow_rows.append({
            "종목명": info.get("name"),
            "티커": info.get("ticker"),
            "기간": f"{flow.get('period_start','')} ~ {flow.get('period_end','')}",
            "개인": flow.get("개인"),
            "기관합계": flow.get("기관합계"),
            "외국인합계": flow.get("외국인합계"),
            "기타법인": flow.get("기타법인"),
            "비고": flow.get("error", ""),
        })
    st.dataframe(pd.DataFrame(flow_rows), use_container_width=True)

    st.header("4. 뉴스")
    for r in results:
        info = r["resolved"]
        st.subheader(f"{info.get('name')} ({info.get('ticker')})")

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("#### 국내 뉴스")
            for n in r["news"].get("domestic", [])[:max_news]:
                title = n.get("title", "")
                link = n.get("link", "")
                source = n.get("source", "")
                published = n.get("published", "")
                if link:
                    st.markdown(f"- [{title}]({link})  \n  `{source}` `{published}`")
                else:
                    st.markdown(f"- {title}  \n  `{source}` `{published}`")

        with c2:
            st.markdown("#### 해외 뉴스")
            overseas = r["news"].get("overseas", [])[:max_news]
            translated_bundle = ""
            if overseas:
                translated_bundle = overseas[0].get("translated_bundle", "")

            if translated_bundle:
                with st.expander("영어 뉴스 한국어 번역/요약 보기", expanded=False):
                    st.write(translated_bundle)

            for n in overseas:
                title = n.get("title", "")
                link = n.get("link", "")
                source = n.get("source", "")
                published = n.get("published", "")
                if link:
                    st.markdown(f"- [{title}]({link})  \n  `{source}` `{published}`")
                else:
                    st.markdown(f"- {title}  \n  `{source}` `{published}`")

        if r.get("errors"):
            with st.expander("오류/경고"):
                for e in r["errors"]:
                    st.warning(e)

    st.header("5. AI 최종 투자 브리핑")
    report_text = st.session_state.briefing_report or ""
    st.markdown(report_text)

    st.download_button(
        label="📄 최종 리포트 Markdown 다운로드",
        data=report_text.encode("utf-8"),
        file_name=f"stock_briefing_{today_kst().isoformat()}.md",
        mime="text/markdown",
    )

    st.download_button(
        label="🧾 원본 JSON 다운로드",
        data=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name=f"stock_briefing_payload_{today_kst().isoformat()}.json",
        mime="application/json",
    )

    st.header("6. Gmail로 최종 리포트 발송")
    with st.form("gmail_form"):
        default_subject = f"AI 주식 브리핑 - {today_kst().isoformat()}"
        recipient = st.text_input("수신 이메일 주소", placeholder="recipient@example.com")
        subject = st.text_input("메일 제목", value=default_subject)
        attach_json = st.checkbox("원본 JSON 데이터도 첨부", value=True)
        submitted = st.form_submit_button("📧 Gmail 발송")

        if submitted:
            if not recipient:
                st.error("수신 이메일 주소를 입력하세요.")
            elif not is_valid_email(recipient):
                st.error("이메일 주소 형식이 올바르지 않습니다.")
            elif not report_text.strip():
                st.error("발송할 리포트가 비어 있습니다.")
            else:
                ok, msg = send_report_email(
                    recipient=recipient,
                    subject=subject,
                    report_markdown=report_text,
                    payload=payload if attach_json else None,
                )
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

    st.header("7. 원본 JSON")
    with st.expander("수집/분석 원본 데이터"):
        st.json(payload)

st.divider()
st.caption("본 앱은 투자 참고용 분석 도구이며, 특정 종목의 매수·매도 확정 권유가 아닙니다.")
