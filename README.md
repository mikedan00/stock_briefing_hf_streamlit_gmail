# AI Stock Briefing: PyKRX + yfinance + HF Router + Gmail

사용자가 입력한 최대 10개 종목에 대해 최신 종가, 국내/해외 뉴스, 주가 추이, 수급, 내일 예상 방향과 예상 등락률을 분석하고, Hugging Face Router LLM으로 최종 투자 브리핑을 생성한 뒤 Gmail로 발송할 수 있는 Streamlit 앱입니다.

## 주요 기능

### 1. 가격 수집
- 국내 종목: PyKRX 사용
- 해외 종목: yfinance 사용
- 오늘이 주말 또는 휴장일이면 가장 최근 거래일 종가를 자동 사용
- 입력 예시:
  ```text
  삼성전자, SK하이닉스, 005930, 000660, AAPL, MSFT, NVDA
  ```

### 2. 뉴스 수집
- 국내 뉴스:
  - Google News RSS
  - Naver News 검색 HTML fallback
- 해외 뉴스:
  - Google News RSS 영어
  - yfinance/Yahoo Finance news
- 영어 뉴스는 Hugging Face Router LLM으로 한국어 번역/요약

### 3. 투자 브리핑
- 최신 종가
- 이번주, 이번달, 6개월 수익률
- 5/20/60일 이동평균
- 20일 변동성
- 국내 종목 외국인/기관/개인 수급
- 내일 예상 방향: UP / DOWN / NEUTRAL
- 예상 상승/하락률
- 투자전략, 내일 매매전략, 리스크

### 4. Gmail 발송
- 생성된 최종 리포트를 사용자가 입력한 이메일 주소로 발송
- Gmail App Password 기반 SMTP 사용
- Streamlit Cloud Secrets와 로컬 `.env` 모두 지원

---

## 로컬 VS Code 실행

```bash
cd stock_briefing_hf_streamlit_gmail
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
streamlit run app.py
```

macOS/Linux:

```bash
cd stock_briefing_hf_streamlit_gmail
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

---

## `.env` 설정

```env
HF_TOKEN=hf_본인토큰
HF_ROUTER_URL=https://router.huggingface.co/v1
HF_MODEL_ID=google/gemma-4-26B-A4B-it

GMAIL_SENDER=yourgmail@gmail.com
GMAIL_APP_PASSWORD=구글앱비밀번호
```

> 사용자가 적은 `google/gemma4-b26-A4b`는 실제 Hugging Face 모델 ID 형식과 다를 수 있으므로 `HF_MODEL_ID`는 설정에서 자유롭게 바꿀 수 있게 했습니다.

---

## Gmail App Password 발급 방법

1. Google 계정 접속
2. 보안
3. 2단계 인증 켜기
4. 앱 비밀번호 생성
5. 앱 이름 예: `Streamlit Stock Briefing`
6. 생성된 16자리 비밀번호를 `GMAIL_APP_PASSWORD`에 입력

일반 Gmail 로그인 비밀번호가 아니라 **앱 비밀번호**를 사용해야 합니다.

---

## Streamlit Cloud 배포

1. GitHub에 프로젝트 업로드
2. Streamlit Cloud → New app
3. Repository 선택
4. Main file path: `app.py`
5. Advanced settings → Secrets에 아래 입력

```toml
HF_TOKEN = "hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
HF_ROUTER_URL = "https://router.huggingface.co/v1"
HF_MODEL_ID = "google/gemma-4-26B-A4B-it"

GMAIL_SENDER = "yourgmail@gmail.com"
GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"
```

6. Deploy

---

## 주의사항

- 본 앱은 투자 참고용입니다.
- 내일 예상 방향과 예상 등락률은 가격/수급/뉴스 기반 휴리스틱과 LLM 요약 결과입니다.
- 실제 매수·매도 판단에는 공시, 실적, 환율, 시장지수, 거시 이벤트, 리스크 관리가 함께 필요합니다.
- Naver News는 공식 API 없이 HTML fallback으로 구현되어 있어 네이버 페이지 구조가 바뀌면 일부 수집이 실패할 수 있습니다.
