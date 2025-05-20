###############################################
# bot.py — Sheets→GPT→X 自動投稿 1日3回版
# 2025‑05‑18 : 高品質"気づきツイート"生成プロンプトを統合
###############################################

import os, re, json, datetime, textwrap, random, math
from typing import List, Dict, Any

import tweepy, openai, gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# ── 環境変数 ────────────────────────────────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
API_KEY, API_SECRET = os.getenv("API_KEY"), os.getenv("API_SECRET")
ACCESS_TOKEN, ACCESS_SECRET = os.getenv("ACCESS_TOKEN"), os.getenv("ACCESS_SECRET")
SHEET_URL = os.getenv("SHEET_URL")
SERVICE_JSON = os.getenv("GOOGLE_SERVICE_JSON")

client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET,
    wait_on_rate_limit=True,
)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
if os.path.isfile(str(SERVICE_JSON)):
    creds = Credentials.from_service_account_file(SERVICE_JSON, scopes=SCOPES)
else:
    creds = Credentials.from_service_account_info(json.loads(SERVICE_JSON), scopes=SCOPES)

gc = gspread.authorize(creds)
sheet = gc.open_by_url(SHEET_URL).sheet1

# ── 制限テーマ ──────────────────────────────
THEMES = [
    "美容師のインスタ集客",
    "美容師の集客",
    "美容師の経営戦略",
    "美容室経営者向け情報",
    "美容師の生成AI活用",
]
THEME_REGEX = re.compile("|".join(re.escape(t) for t in THEMES))
EMOJIS = ["🎯", "💡", "✨", "📈", "🚀"]
MODEL = "gpt-4o-mini"
MAX_LEN = 140

# ── 新しい高品質ツイート生成プロンプト ─────────
PROMPT_TEMPLATE = rf"""
あなたはローカルビジネス（美容室・整骨院・個人店など）のマーケティングを専門とするリサーチャー兼コピーライターです。

## Audience
現場で集客・リピート対策を任されている経営者・店長

## Goal
100〜140文字の日本語ツイートを {{N}} 本生成する。
読んだ相手が『試してみよう』と思う一次情報（数値・調査結果）や顧客心理の“事実”を共有すること。

## Content Rules
1. **ファクト必須**  
   ・2022年以降の信頼できる公式データのみ  
   ・数値を最低1つ含める  
2. **文字数** 全角換算100〜140。範囲外なら自動で調整  
3. **書式** 一人称『私』視点の気づきメモ。絵文字・ハッシュタグ・セールス語禁止。  
   ファクト末尾に簡潔出典 (◯◯調査2024) を括弧書き  
4. **ジャンル比率** マーケ戦術40％ / 顧客心理40％ / デジタル効率化20％  
5. **重複禁止** テーマ・数字・出典が被らない  
6. **品質チェック** 条件外は自動再生成  

## Output Format
JSON 配列で以下の形式
[
  {{"tweet": "ここに100〜140文字の投稿文", "source": "出典URLまたはDOI"}}
]
"""
あなたはローカルビジネス（美容室・整骨院・個人店など）のマーケティングを専門とするリサーチャー兼コピーライターです。

## Audience
現場で集客・リピート対策を任されている経営者・店長

## Goal
100〜140文字の日本語ツイートを {N} 本生成する。読んだ相手が『試してみよう』と思う一次情報（数値・調査結果）や顧客心理の“事実”を共有すること。

## Content Rules
1. **ファクト必須**  
   ・2022年以降の信頼できる公式データのみ  
   ・数値を最低1つ含める
2. **文字数** 全角換算100〜140。範囲外なら自動で調整
3. **書式** 一人称『私』視点の気づきメモ。絵文字・ハッシュタグ・セールス語禁止。ファクト末尾に簡潔出典 (◯◯調査2024) を括弧書き
4. **ジャンル比率** マーケ戦術40％ / 顧客心理40％ / デジタル効率化20％
5. **重複禁止** テーマ・数字・出典が被らない
6. **品質チェック** 条件外は自動再生成

## Output Format
JSON 配列で
[
  {{"tweet": "ここに100〜140文字の投稿文", "source": "出典URLまたはDOI"}}
]
"""
あなたはローカルビジネス（美容室・整骨院・個人店など）のマーケティングを専門とするリサーチャー兼コピーライターです。

## Audience
現場で集客・リピート対策を任されている経営者・店長

## Goal
100〜140文字の日本語ツイートを {N} 本生成する。読んだ相手が『試してみよう』と思う一次情報（数値・調査結果）や顧客心理の“事実”を共有すること。

## Content Rules
1. **ファクト必須**  
   ・2022年以降の信頼できる公式データのみ  
   ・数値を最低1つ含める
2. **文字数** 全角換算100〜140。範囲外なら自動で調整
3. **書式** 一人称『私』視点の気づきメモ。絵文字・ハッシュタグ・セールス語禁止。ファクト末尾に簡潔出典 (◯◯調査2024) を括弧書き
4. **ジャンル比率** マーケ戦術40％ / 顧客心理40％ / デジタル効率化20％
5. **重複禁止** テーマ・数字・出典が被らない
6. **品質チェック** 条件外は自動再生成

## Output Format
JSON 配列で
[
  {"tweet": "ここに100〜140文字の投稿文", "source": "出典URLまたはDOI"}
]
"""

RE_JSON_ARRAY = re.compile(r"\[.*\]", re.S)

# ── GPT ヘルパー ─────────────────────────

def generate_tweet(raw: str) -> List[str]:
    """1 つの OCR 原文から 1 本の高品質ツイートを返す"""
    # まず PROMPT_TEMPLATE で N=1 本要求
    prompt = PROMPT_TEMPLATE.format(N=1)
    payload = f"原文:\n{raw}"
    res = openai.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}, {"role": "user", "content": payload}],
        temperature=0.9,
    ).choices[0].message.content.strip()

    json_match = RE_JSON_ARRAY.search(res)
    if not json_match:
        raise ValueError("GPT output is not valid JSON array")
    data = json.loads(json_match.group(0))
    tweet_text = data[0]["tweet"]
    # 強制 140 字以内調整
    if len(tweet_text) > MAX_LEN:
        tweet_text = tweet_text[:MAX_LEN]
    return [tweet_text]

# ── Twitter 投稿 & シート更新 ───────────────

def post_and_update(idx: int, tweet_list: List[str]):
    root = client.create_tweet(text=tweet_list[0])
    reply_to = root.data["id"]
    for t in tweet_list[1:]:
        tw = client.create_tweet(text=t, in_reply_to_tweet_id=reply_to)
        reply_to = tw.data["id"]

    sheet.batch_update([
        {"range": f"F{idx}", "values": [[True]]},
        {"range": f"G{idx}", "values": [[datetime.datetime.now().isoformat()]]},
    ])

# ── メイン処理 ────────────────────────────

def process_one_row():
    rows = sheet.get_all_records()
    fallback_idx: int | None = None

    for idx, row in enumerate(rows, start=2):
        if row.get("Posted"):
            continue
        raw_text = row.get("抽出テキスト", "").strip()
        if not raw_text:
            continue
        if THEME_REGEX.search(raw_text):
            tweets = generate_tweet(raw_text)
            post_and_update(idx, tweets)
            print(f"✅ Posted themed row {idx}")
            return
        if fallback_idx is None:
            fallback_idx = idx

    if fallback_idx:
        raw_text = rows[fallback_idx - 2]["抽出テキスト"].strip()
        tweets = generate_tweet(raw_text)
        post_and_update(fallback_idx, tweets)
        print(f"⚠️  Fallback posted row {fallback_idx}")
    else:
        print("🚫 No unposted rows available.")


if __name__ == "__main__":
    process_one_row()
