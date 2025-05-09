# bot.py — UTF-8 safe & 120–140字×最大3ツイートの情報濃いスレッド
# ================================================================
# requirements.txt
#   openai>=1.3.0
#   tweepy>=4.14.0
#   python-dotenv>=1.0.1

import os
import re
import random
import time
import hashlib
import datetime
import unicodedata
from pathlib import Path

import openai
import tweepy
from dotenv import load_dotenv

# ─────────────────── 環境変数 ──────────────────────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

API_KEY        = os.getenv("API_KEY")
API_SECRET     = os.getenv("API_SECRET")
ACCESS_TOKEN   = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET  = os.getenv("ACCESS_SECRET")

client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET,
)

LOG_DIR = Path("tweet_logs")
LOG_DIR.mkdir(exist_ok=True)

# ── プロンプト設定 ────────────────────────────────
TEMPLATES = [
    "質問フック型", "驚き事例型",
    "課題解決ステップ型", "ストーリー共感型"
]

PROMPT_CORE = (
    "あなたはSNSマーケティングのプロです。"
    "ローカルビジネス経営者やフリーランス（美容師・歯科医師・小売店・士業・コーチなど）に向けて、"
    "ChatGPT活用の小ネタを紹介するX（旧Twitter）の投稿を作成してください。\n"
    "出力は必ず次の形式で:\n"
    "Tweet1: ……\nTweet2: ……\nTweet3: ……（必要な場合のみ）\n"
    "Tweet1 は100–140字で1回改行を入れ、数字やインパクトのある表現を含めること。\n"
    "Tweet2 以降は120–140字で箇条書き可。最後は読者へ行動を促す。"
)

MIN_LEN, MAX_LEN = 100, 140    # 先頭ツイート長さの下限/上限

# ── ユーティリティ ───────────────────────────────
def _clean(text: str) -> str:
    """サロゲート残りや制御文字を除去して UTF-8 セーフに"""
    text = unicodedata.normalize("NFC", text)
    return text.encode("utf-8", "ignore").decode("utf-8", "ignore")

def _insert_break(text: str, limit: int = 120) -> str:
    """limit 字以内に収めつつ自然な改行を1つ挿入"""
    text = text.strip()
    if len(text) <= limit:
        return text
    # 句読点優先で切る
    for mark in "。.!?！？":
        pos = text.rfind(mark, 50, limit)
        if pos != -1:
            return text[:pos + 1] + "\n" + text[pos + 1:]
    # 句読点が無ければ中央で折り返し
    mid = limit
    return text[:mid] + "\n" + text[mid:]

def valid_first(t: str) -> bool:
    return MIN_LEN <= len(t) <= MAX_LEN

# ── スレッド生成 ────────────────────────────────
def _parse_tweets(raw: str) -> list[str]:
    parts = re.findall(r"Tweet\d+:\s*(.+)", raw, flags=re.I)
    if not parts:
        parts = [p.strip() for p in raw.split("\n") if p.strip()]
    return parts

def generate_thread() -> list[str]:
    template = random.choice(TEMPLATES)
    prompt = f"{PROMPT_CORE}\n# テンプレート: {template}"
    for _ in range(5):                     # 最大5回チャレンジ
        rsp = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=220,
            temperature=0.9,
        )
        raw = _clean(rsp.choices[0].message.content)
        parts = _parse_tweets(raw)
        if len(parts) < 2:
            continue
        parts[0] = _insert_break(parts[0])
        if valid_first(parts[0]):
            break
    else:
        # フォールバック 1：条件緩和（90字〜）
        fb_prompt = PROMPT_CORE.replace("100–140", "90–140")
        rsp = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": fb_prompt}],
            max_tokens=220,
            temperature=0.9,
        )
        raw = _clean(rsp.choices[0].message.content)
        parts = _parse_tweets(raw)

    if not parts:
        raise RuntimeError("ChatGPTからツイートを取得できませんでした")

    # 1本しか無ければ強制分割
    if len(parts) == 1:
        text = parts[0]
        split = max(60, len(text) // 2)
        parts = [text[:split], text[split:]]

    # 文字数整形・トリム
    trimmed = []
    for p in parts[:3]:
        p = p.strip()
        if len(p) > MAX_LEN:
            p = p[:MAX_LEN - 1] + "…"
        trimmed.append(p)
    return [_clean(t) for t in trimmed if t.strip()]

# ── 投稿関連 ────────────────────────────────
def _hash_today(text: str) -> str:
    today = datetime.date.today().isoformat()
    return hashlib.md5((today + text).encode()).hexdigest()

def is_duplicate(text: str) -> bool:
    h = _hash_today(text)
    log_file = LOG_DIR / f"{datetime.date.today():%Y%m%d}.log"
    if log_file.exists() and h in log_file.read_text().split():
        return True
    log_file.write_text((log_file.read_text() if log_file.exists() else "") + h + "\n")
    return False

def post_thread(parts: list[str]):
    # 空文字除去
    parts = [p for p in parts if p.strip()]

    head_id = client.create_tweet(text=parts[0]).data["id"]
    print("Tweeted:", parts[0])

    for body in parts[1:]:
        time.sleep(2)
        client.create_tweet(text=body, in_reply_to_tweet_id=head_id)
        print(" replied:", body[:40], "...")

# ── main ─────────────────────────────────────
def main():
    parts = generate_thread()
    if is_duplicate(parts[0]):
        print("Duplicate detected. Skip posting.")
        return
    try:
        post_thread(parts)
    except Exception as e:
        print("⚠️ thread post failed:", e)
        # 先頭だけでも投稿
        client.create_tweet(text=parts[0][:MAX_LEN])
        print("Posted head only due to error")

if __name__ == "__main__":
    main()
