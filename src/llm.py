\
from __future__ import annotations

from openai import OpenAI
from .config import HF_TOKEN, HF_ROUTER_URL, HF_MODEL_ID

def hf_chat(messages: list[dict], temperature: float = 0.25, max_tokens: int = 1800) -> str:
    if not HF_TOKEN:
        return "HF_TOKEN이 설정되지 않아 LLM 작업을 실행하지 못했습니다. .env 또는 Streamlit Secrets에 HF_TOKEN을 입력하세요."

    client = OpenAI(
        base_url=HF_ROUTER_URL,
        api_key=HF_TOKEN,
    )

    try:
        resp = client.chat.completions.create(
            model=HF_MODEL_ID,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        return (
            "HF Router 호출 실패: "
            f"{type(e).__name__}: {e}\n\n"
            "확인 항목: HF_MODEL_ID, HF_TOKEN, Inference Provider 활성화, 모델 라이선스 동의, 쿼터/과금 상태."
        )

def translate_english_news_to_korean(items: list[dict], stock_name: str) -> list[dict]:
    if not items:
        return items
    if not HF_TOKEN:
        return items

    joined = "\n".join(
        f"{i+1}. title={x.get('title','')}\nsummary={x.get('summary','')}\nsource={x.get('source','')}"
        for i, x in enumerate(items[:10])
    )
    prompt = f"""
다음은 {stock_name} 관련 영어 뉴스 목록이다.
각 항목의 제목과 요약을 한국어로 자연스럽게 번역하라.
뉴스의 의미를 보존하고, 투자 판단에 영향을 주는 표현은 과장하지 말라.

출력 형식:
1.
- 한국어 제목:
- 한국어 요약:
- 투자 관점 시사점:

{joined}
"""
    translated = hf_chat(
        [
            {"role": "system", "content": "너는 금융뉴스 전문 번역가이자 주식시장 애널리스트다."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=1800,
    )

    for x in items:
        x["translated_bundle"] = translated
    return items

def make_final_briefing(payload: dict) -> str:
    system = """
너는 한국어로 기관투자자 스타일의 데일리 주식 브리핑을 작성하는 주식 투자전략 애널리스트다.
다만 특정 종목 매수/매도 확정 권유가 아니라, 데이터 기반 시나리오와 리스크 관리 중심으로 작성한다.
가격, 수급, 기술적 추세, 국내뉴스, 해외뉴스를 종합해 내일 장 대응 전략을 만든다.
예상 상승/하락률은 확률적 추정치이므로 보수적으로 범위로 제시한다.
"""
    user = f"""
아래 JSON 데이터를 기반으로 최종 리포트를 작성하라.

필수 형식:

# 오늘의 주식 브리핑

## 1. 핵심 요약
- 시장/종목별 핵심 포인트
- 가장 강한 종목
- 가장 주의할 종목

## 2. 종목별 상세 분석
각 종목마다 아래 항목을 포함:
- 최신 종가와 기준 거래일
- 이번주/이번달/6개월 주가 추이
- 5일/20일/60일 이동평균 관점
- 외국인/기관/개인 수급. 해외 종목은 거래량과 추세로 대체
- 국내뉴스 3줄 요약
- 해외뉴스 3줄 요약
- 내일 예상 방향: UP / DOWN / NEUTRAL
- 예상 등락률 범위
- 매매전략: 진입, 분할매수, 익절, 손절, 관망 기준

## 3. 통합 투자전략
- 단기 트레이딩 관점
- 스윙 관점
- 리스크 관리

## 4. 내일 장 체크리스트
- 장 시작 전 확인할 것
- 장중 확인할 것
- 종가 전 확인할 것

## 5. 리스크와 면책
- 예측 한계
- 투자자 본인 판단 필요

데이터:
{payload}
"""
    return hf_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.25,
        max_tokens=4200,
    )
