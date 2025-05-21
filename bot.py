# -*- coding: utf-8 -*-
###############################################
# bot.py — Sheets→GPT→X 自動投稿 1日5回版 (robust JSON / function-calling)
###############################################
"""
● 変更点
1. OpenAI *function calling* で JSON を強制 ⇒ 正規表現不要
2. Sheets 503 対応 (指数バックオフ 3 回)
3. GPT 応答が欠落した場合は 3 再試行 (temperature 0.7 → 0.9)
4. 投稿は 1 ツイート（140 字以内）固定
"""

import os, json, time, datetime, re
from typing import List

import tweepy, openai, gspread
from gspread.exceptions import APIError
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# ────────────────── 環境変数 ──────────────────
load_dotenv()
openai.api_key  = os.getenv("OPENAI_API_KEY")
API_KEY         = os.getenv("API_KEY")
API_SECRET      = os.getenv("API_SECRET")
ACCESS_TOKEN    = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET   = os.getenv("ACCESS_SECRET")
SHEET_URL       = os.getenv("SHEET_URL")
SERVICE_JSON    = os.getenv("GOOGLE_SERVICE_JSON")

# ────────────────── Twitter ───────────────────
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET,
    wait_on_rate_limit=True,
)

# ────────────────── Google Sheets ────────────
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
if SERVICE_JSON and os.path.isfile(SERVICE_JSON):
    creds = Credentials.from_service_account_file(SERVICE_JSON, scopes=SCOPES)
else:
    creds = Credentials.from_service_account_info(json.loads(SERVICE_JSON), scopes=SCOPES)

gc = gspread.authorize(creds)


def open_sheet_retry(url: str, tries: int = 3, base_wait: int = 5):
    for i in range(tries):
        try:
            return gc.open_by_url(url).sheet1
        except APIError as e:
            if getattr(e.response, "status_code", 0) >= 500:
                wait = base_wait * (2 ** i)
                print(f"⚠️  Sheets 5xx ({e.response.status_code}). retry in {wait}s…")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Sheets API unavailable after retries")

sheet = open_sheet_retry(SHEET_URL)

# ────────────────── GPT settings ─────────────
MODEL   = "gpt-4o-mini"
MAX_LEN = 140

THEME_REGEX = re.compile("|".join(map(re.escape, [
    "美容師のインスタ集客",
    "美容師の集客",
    "美容師の経営戦略",
    "美容室経営者向け情報",
    "美容師の生成AI活用",
])))

SYSTEM_PROMPT = (
    "あなたはローカルビジネス（美容室・整骨院・個人店など）のマーケティングを専門とするコンサルタント兼リサーチャーです。"
    "日本語で140文字以内のツイートを1本生成してください。"
    "●2022年以降の信頼できる統計・公式データを必ず1つ含める"
    "●一人称『私』で気づきを共有するトーン（美容師ではなくコンサル視点）"
    "●絵文字・ハッシュタグ・販促ワードは禁止"
    "●出典は返却 JSON の source にのみ入れ、ツイート文には書かない"
)

FUNCTION_SCHEMA = {
    "name": "make_tweet",
    "parameters": {
        "type": "object",
        "properties": {
            "tweet":  {"type": "string", "description": "140字以内のツイート本文"},
            "source": {"type": "string", "description": "参照元のURLまたはDOI"}
        },
        "required": ["tweet", "source"]
    }
}


def gpt_tweet(raw: str, retries: int = 3) -> str:
    prompt = SYSTEM_PROMPT
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"原文:\n{raw}"}
    ]
    temp = 0.7
    for _ in range(retries):
        resp = openai.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=[{"type": "function", "function": FUNCTION_SCHEMA}],
            tool_choice={"type": "function", "function": {"name": "make_tweet"}},
            temperature=temp,
        )
        args_json = resp.choices[0].message.tool_calls[0].function.arguments
        try:
            data = json.loads(args_json)  # arguments は JSON 文字列
            tweet = data["tweet"]
            if len(tweet) <= MAX_LEN:
                return tweet
        except Exception:
            pass  # 失敗したら再試行
        temp += 0.1  # 温度少し上げて再生成
    raise RuntimeError("GPT failed to return valid tweet <=140 chars")
        temp += 0.1  # 長すぎた場合は温度を上げて再生成
    raise RuntimeError("GPT failed to return <=140 chars")

# ────────────────── Posting & Sheet ──────────

def post_and_update(idx: int, text: str):
    client.create_tweet(text=text)
    sheet.update(f"F{idx}:G{idx}", [[True, datetime.datetime.now().isoformat()]])

# ────────────────── Main ─────────────────────

def process():
    rows = sheet.get_all_records()
    fallback = None
    for idx, row in enumerate(rows, start=2):
        if row.get("Posted"):
            continue
        txt = (row.get("抽出テキスト") or "").strip()
        if not txt:
            continue
        if THEME_REGEX.search(txt):
            tweet = gpt_tweet(txt)
            post_and_update(idx, tweet)
            print("✅ Posted themed row", idx)
            return
        if fallback is None:
            fallback = (idx, txt)

    if fallback:
        idx, txt = fallback
        tweet = gpt_tweet(txt)
        post_and_update(idx, tweet)
        print("⚠️  Fallback posted row", idx)
    else:
        print("🚫 No unposted rows")

if __name__ == "__main__":
    process()
