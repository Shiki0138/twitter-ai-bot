# -*- coding: utf-8 -*-
###############################################
# bot.py — Sheets→GPT→X 自動投稿 1日5回版 (retry fix)
###############################################

import os, re, json, datetime, random, time
from typing import List

import tweepy, openai, gspread
from gspread.exceptions import APIError
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# ── 環境変数 ────────────────────────────────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
API_KEY        = os.getenv("API_KEY")
API_SECRET     = os.getenv("API_SECRET")
ACCESS_TOKEN   = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET  = os.getenv("ACCESS_SECRET")
SHEET_URL      = os.getenv("SHEET_URL")
SERVICE_JSON   = os.getenv("GOOGLE_SERVICE_JSON")

# ── Twitter クライアント ───────────────────
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET,
    wait_on_rate_limit=True,
)

# ── Google Sheets クライアント ──────────────
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
if SERVICE_JSON and os.path.isfile(SERVICE_JSON):
    creds = Credentials.from_service_account_file(SERVICE_JSON, scopes=SCOPES)
else:
    creds = Credentials.from_service_account_info(json.loads(SERVICE_JSON), scopes=SCOPES)

gc = gspread.authorize(creds)

# === 503 対策: リトライ付きでシートを開く ===

def open_sheet_with_retry(url: str, tries: int = 3, base_wait: int = 5):
    for i in range(tries):
        try:
            return gc.open_by_url(url).sheet1
        except APIError as e:
            status = getattr(e.response, "status_code", 0)
            if status >= 500:  # 5xx のときだけ再試行
                wait = base_wait * (2 ** i)
                print(f"⚠️  Sheets API {status}. retry in {wait}s…")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Google Sheets API unavailable after retries")

sheet = open_sheet_with_retry(SHEET_URL)

# ── 定数 ────────────────────────────────────
THEMES      = [
    "美容師のインスタ集客",
    "美容師の集客",
    "美容師の経営戦略",
    "美容室経営者向け情報",
    "美容師の生成AI活用",
]
THEME_REGEX = re.compile("|".join(re.escape(t) for t in THEMES))
MODEL   = "gpt-4o-mini"
MAX_LEN = 140

# ── PROMPT TEMPLATE ─────────────────────────
PROMPT_TEMPLATE = r"""
あなたはローカルビジネス（美容室・整骨院・個人店など）のマーケティングを専門とするコンサルタント兼リサーチャーです。

## Audience
現場で集客・リピート対策を任されている経営者・店長

## Goal
100〜140文字の日本語ツイートを {N} 本生成する。
読んだ相手が『試してみよう』と思う一次情報（数値・調査結果）や顧客心理の“事実”を共有すること。

## Content Rules
1. **ファクト必須**  
   ・2022年以降の信頼できる公式データのみ  
   ・数値を最低1つ含める  
2. **文字数** 全角換算100〜140。範囲外なら自動で調整  
3. **書式** 一人称『私』視点の気づきメモ。ただし **美容師ではなくマーケティングコンサルタントとして** 書く。絵文字・ハッシュタグ・セールス語禁止。  
   ファクト末尾に簡潔出典 (◯◯調査2024) を括弧書き  
4. **ジャンル比率** マーケ戦術40％ / 顧客心理40％ / デジタル効率化20％  
5. **重複禁止** テーマ・数字・出典が被らない  
6. **品質チェック** 条件外は自動再生成  

## Output Format
JSON 配列のみを返す
[
  {{\"tweet\": \"ここに100〜140文字の投稿文\", \"source\": \"出典URLまたはDOI\"}}
]
"""

RE_JSON_ARRAY = re.compile(r"\[.*?\]", re.S)

# ── GPT helper ─────────────────────────────

def generate_tweet(raw: str, retry: int = 3) -> List[str]:
    prompt = PROMPT_TEMPLATE.format(N=1)
    for _ in range(retry):
        res = openai.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "user", "content": f"原文:\n{raw}"},
            ],
            temperature=0.7,
        ).choices[0].message.content

        m = RE_JSON_ARRAY.search(res.replace("```json", "").replace("```", ""))
        if m:
            try:
                tweet = json.loads(m.group(0))[0]["tweet"]
                return [tweet[:MAX_LEN]]
            except Exception:
                continue  # パース失敗→再試行
    raise RuntimeError("GPT failed to return valid JSON")

# ── Posting & sheet update ─────────────────

def post_and_mark(idx: int, tweets: List[str]):
    client.create_tweet(text=tweets[0])
    sheet.update(f"F{idx}:G{idx}", [[True, datetime.datetime.now().isoformat()]])

# ── Main ───────────────────────────────────

def process():
    rows = sheet.get_all_records()
    fallback = None
    for idx, row in enumerate(rows, start=2):
        if row.get("Posted"):
            continue
        text = row.get("抽出テキスト", "").strip()
        if not text:
            continue
        if THEME_REGEX.search(text):
            t = generate_tweet(text)
            post_and_mark(idx, t)
            print("✅ Posted themed row", idx)
            return
        if fallback is None:
            fallback = (idx, text)
    if fallback:
        idx, text = fallback
        t = generate_tweet(text)
        post_and_mark(idx, t)
        print("⚠️  Fallback posted row", idx)
    else:
        print("🚫 No unposted rows")

if __name__ == "__main__":
    process()
