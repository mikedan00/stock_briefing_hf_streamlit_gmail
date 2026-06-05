\
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

def get_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, None)
        if value:
            return str(value)
    except Exception:
        pass
    return os.getenv(name, default)

HF_TOKEN = get_secret("HF_TOKEN", "")
HF_ROUTER_URL = get_secret("HF_ROUTER_URL", "https://router.huggingface.co/v1")
HF_MODEL_ID = get_secret("HF_MODEL_ID", "google/gemma-4-26B-A4B-it")

GMAIL_SENDER = get_secret("GMAIL_SENDER", "")
GMAIL_APP_PASSWORD = get_secret("GMAIL_APP_PASSWORD", "")

MAX_TICKERS = 10
