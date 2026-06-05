\
from __future__ import annotations

import smtplib
import re
import json
from email.message import EmailMessage
from email.utils import formataddr
from html import escape

from .config import GMAIL_SENDER, GMAIL_APP_PASSWORD
from .utils import now_kst_str

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def is_valid_email(addr: str) -> bool:
    return bool(EMAIL_RE.match(addr.strip()))

def markdown_to_basic_html(markdown_text: str) -> str:
    """
    외부 markdown 라이브러리 없이 이메일 본문용 최소 HTML 변환.
    Streamlit Cloud 패키지 충돌을 줄이기 위한 단순 변환.
    """
    lines = markdown_text.splitlines()
    html_lines = []
    in_ul = False

    for line in lines:
        raw = line.rstrip()
        s = raw.strip()

        if not s:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append("<br>")
            continue

        if s.startswith("# "):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append(f"<h1>{escape(s[2:])}</h1>")
        elif s.startswith("## "):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append(f"<h2>{escape(s[3:])}</h2>")
        elif s.startswith("### "):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append(f"<h3>{escape(s[4:])}</h3>")
        elif s.startswith("- "):
            if not in_ul:
                html_lines.append("<ul>")
                in_ul = True
            html_lines.append(f"<li>{escape(s[2:])}</li>")
        else:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append(f"<p>{escape(s)}</p>")

    if in_ul:
        html_lines.append("</ul>")

    return """
    <html>
    <body style="font-family: Arial, sans-serif; line-height:1.55; color:#222;">
    <div style="max-width: 920px; margin: 0 auto;">
    """ + "\n".join(html_lines) + """
    <hr>
    <p style="font-size:12px;color:#666;">
    이 메일은 AI Stock Briefing Streamlit 앱에서 자동 생성되었습니다.
    투자 참고용이며 매수·매도 확정 권유가 아닙니다.
    </p>
    </div>
    </body>
    </html>
    """

def send_report_email(
    recipient: str,
    subject: str,
    report_markdown: str,
    payload: dict | None = None,
    sender_name: str = "AI Stock Briefing",
) -> tuple[bool, str]:
    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        return False, "GMAIL_SENDER 또는 GMAIL_APP_PASSWORD가 설정되지 않았습니다."

    recipient = recipient.strip()
    if not is_valid_email(recipient):
        return False, "수신 이메일 주소 형식이 올바르지 않습니다."

    if not subject.strip():
        subject = f"AI 주식 브리핑 - {now_kst_str()}"

    msg = EmailMessage()
    msg["From"] = formataddr((sender_name, GMAIL_SENDER))
    msg["To"] = recipient
    msg["Subject"] = subject

    plain = report_markdown.strip() or "리포트 본문이 비어 있습니다."
    html = markdown_to_basic_html(plain)

    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")

    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        msg.add_attachment(
            data,
            maintype="application",
            subtype="json",
            filename="stock_briefing_payload.json",
        )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
            smtp.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        return True, f"{recipient} 주소로 리포트를 발송했습니다."
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail 인증 실패: Gmail 계정, 2단계 인증, App Password를 확인하세요."
    except Exception as e:
        return False, f"Gmail 발송 실패: {type(e).__name__}: {e}"
