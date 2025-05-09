# bot.py — GPT‑4o-mini版：驚きと数字のある濃いスレッド自動投稿
# ================================================================
# ライブラリ
#   openai>=1.3.0  (GPT‑4o-mini 対応)
#   tweepy>=4.14.0
#   python-dotenv>=1.0.1
# ---------------------------------------------------------------
# 機能概要
#   • ChatGPT(GPT‑4o-mini) に 1 スレッド(2〜3ツイート) を生成させ投稿
#   • Tweet1 は 100〜140 字・改行 1 回・数字や驚き表現を含む
#   • Tweet2/3 は 120〜140 字、ROI や行動促進で締める
#   • 先頭ツイートが条件を満たすまで最大 5 回リトライ → フォールバック
#   • 同日内重複チェック / UTF‑8 セーフ処理 / 280 字カット
# ---------------------------------------------------------------

import os
import re
import random
import time
import unicodedata
import hashlib
import datetime
from pathlib import Path

import openai
import tweepy
from dotenv import load_dotenv

# ─────────────── 環境変数 ────────────────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
MODEL_NAME     = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

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

LOG_DIR = Path("tweet_logs"); LOG_DIR.mkdir(exist_ok=True)

# ─────────────── 設定値 ────────────────
MIN_LEN, MAX_LEN = 100, 140  # 先頭ツイート長さ制限
TEMPLATES = [
    "質問フック型", "驚き事例型", "課題解決ステップ型", "ストーリー共感型"
]
STAT_POOL = [
    "米BPC調査: 中小企業の83%がAIで業務効率化を実感",
    "パナソニックコネクト: 社内ChatGPT導入で年間18.6万時間削減",
    "ロンドン美容室Bleach: SNS×AIで新規予約20%増",
    "歯科医院でリマインド自動化→キャンセル率15%減",
]

PROMPT_CORE = (
    "あなたはSNSマーケティングのプロ兼リサーチャーです。"
    "ローカルビジネス経営者・フリーランスに向けて、ChatGPT活用の驚きの小ネタを日本語で紹介してください。"
    "必ず【数字】か【具体事例】を1つ以上入れます。\n\n"
    "出力は必ず次の形式で:\n"
    "Tweet1: ……\nTweet2: ……\nTweet3: ……（必要なら）\n\n"
    "Tweet1 は100–140字で1回改行を入れ、冒頭に疑問形か驚きの数字を含めてください。\n"
    "Tweet2 と Tweet3 は120–140字。ROIや具体ステップを簡潔に、最後は行動を促す文で締めます。"
)

# ─────────────── ユーティリティ ────────────────

def _clean(text: str) -> str:
    """UTF‑8 セーフ化"""
    text = unicodedata.normalize("NFC", text)
    return text.encode("utf-8", "ignore").decode("utf-8", "ignore")


def _insert_break(text: str, limit: int = 120) -> str:
    """自然改行挿入"""
    text = text.strip()
    if len(text) <= limit:
        return text
    for mark in "。.!?！？":
        pos = text.rfind(mark, 50, limit)
        if pos != -1:
            return text[: pos + 1] + "\n" + text[pos + 1:]
    return text[:limit] + "\n" + text[limit:]


def _parse_tweets(raw: str) -> list[str]:
    parts = re.findall(r"Tweet\d+:\s*(.+)", raw, flags=re.I)
    if not parts:
        parts = [p.strip() for p in raw.split("\n") if p.strip()]
    return parts


def valid_first(t: str) -> bool:
    return MIN_LEN <= len(t) <= MAX_LEN

# ─────────────── スレッド生成 ────────────────

def generate_thread() -> list[str]:
    template = random.choice(TEMPLATES)
    stat     = random.choice(STAT_POOL)
    prompt   = f"{PROMPT_CORE}\n# テンプレート: {template}\n参考統計: {stat}"

    for _ in range(5):
        rsp = openai.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=1.2,
            top_p=1,
        )
        raw = _clean(rsp.choices[0].message.content)
        parts = _parse_tweets(raw)
        if len(parts) < 2:
            continue
        parts[0] = _insert_break(parts[0])
        if valid_first(parts[0]):
            break
    else:
        # フォールバック (条件緩和)
        fb_prompt = prompt.replace("100–140", "90–140")
        rsp = openai.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": fb_prompt}],
            max_tokens=320,
            temperature=1.2,
        )
        raw = _clean(rsp.choices[0].message.content)
        parts = _parse_tweets(raw)

    if not parts:
        raise RuntimeError("ChatGPTからツイートを取得できませんでした")

    if len(parts) == 1:  # 強制分割
        text = parts[0]
        split = max(60, len(text) // 2)
        parts = [text[:split], text[split:]]

    trimmed = []
    for p in parts[:3]:
        p = p.strip()
        if len(p) > MAX_LEN:
            p = p[:MAX_LEN - 1] + "…"
        trimmed.append(_clean(p))
    return [t for t in trimmed if t]

# ─────────────── 投稿関連 ────────────────

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
    parts = [p for p in parts if p.strip()]  # 空除去
    head_id = client.create_tweet(text=parts[0]).data["id"]
    print("Tweeted:", parts[0])
    for body in parts[1:]:
        time.sleep(2)
        client.create_tweet(text=body, in_reply_to_tweet_id=head_id)
        print(" replied:", body[:40], "…")

# ─────────────── main ────────────────

def main():
    parts = generate_thread()
    if is_duplicate(parts[0]):
        print("Duplicate detected. Skip posting.")
        return
    try:
        post_thread(parts)
    except Exception as e:
        print("⚠️ thread post failed:", e)
        client.create_tweet(text=parts[0][:MAX_LEN])
        print("Posted head only due to error")

if __name__ == "__main__":
    main()
