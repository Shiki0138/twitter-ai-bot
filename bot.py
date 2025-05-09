# bot.py — ChatGPT だけでローカルビジネス向けTipsを1スレッド（2ツイート）投稿
# ──────────────────────────────────────────
# 1 日に 5 回このスクリプトを呼び出すと、合計 10 ツイートになります。
# GitHub Actions の cron を 5 本並べて実現してください。
# -------------------------------------------------------------
# requirements.txt
#   openai>=1.3.0
#   tweepy>=4.14.0
#   python-dotenv>=1.0.1
# -------------------------------------------------------------

import os, random, openai, tweepy
from datetime import datetime
from dotenv import load_dotenv

# ── 0. 環境変数 ───────────────────────────────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
TW_CONSUMER_KEY    = os.getenv("API_KEY")
TW_CONSUMER_SECRET = os.getenv("API_SECRET")
TW_ACCESS_TOKEN    = os.getenv("ACCESS_TOKEN")
TW_ACCESS_SECRET   = os.getenv("ACCESS_SECRET")

# ── 1. ネタ候補 ───────────────────────────────
TOPICS = [
    "美容室の空き枠を埋める予約リマインド",
    "口コミ倍増アイデア",
    "Google ビジネスプロフィールのGEO最適化",
    "生成AIで作る時短マニュアル",
    "ChatGPTおもしろ便利活用法"
]

# ── 2. ChatGPT で 2 ツイート生成 ─────────────

def make_thread() -> tuple[str, str]:
    """(tweet_1, tweet_2) を返す。各 140 字以内。"""

    topic = random.choice(TOPICS)

    system_msg = {
        "role": "system",
        "content": (
            "あなたは日本のローカルビジネス（美容室・歯科など）のSNSコンサルタントです。"
            "140字以内のツイートを自然な日本語で書きます。改行は日本人がよく使う\n\nを適宜入れます。"
        )
    }

    user_msg = {
        "role": "user",
        "content": (
            f"テーマ: {topic}\n\n"
            "以下の条件で2ツイート生成してください。\n"
            "- 1つ目: 興味を引く前振り。最後を『▼詳細はリプ欄』で終える。120字程度。\n"
            "- 2つ目: 具体的手順やコツを3個、箇条書き(・)で。各行の間を空行で区切る。\n"
            "- JSON や引用符 (\"\") は使わない。"
        )
    }

    rsp = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[system_msg, user_msg],
        max_tokens=220,
        temperature=0.85,
        frequency_penalty=0.3,
    )

    content = rsp.choices[0].message.content.strip()
    if "###" in content:
        first, second = map(lambda x: x.strip()[:140], content.split("###", 1))
    else:
        # フォーマット崩れ対策：最初の空行で分割
        parts = [p.strip() for p in content.split("\n\n") if p.strip()]
        first, second = parts[0][:140], "\n\n".join(parts[1:])[:140]

    return first, second

# ── 3. Twitter へ投稿 ────────────────────────

def post_thread(tweet1: str, tweet2: str):
    client = tweepy.Client(
        consumer_key=TW_CONSUMER_KEY,
        consumer_secret=TW_CONSUMER_SECRET,
        access_token=TW_ACCESS_TOKEN,
        access_token_secret=TW_ACCESS_SECRET,
    )

    first = client.create_tweet(text=tweet1)
    first_id = first.data.get("id")

    client.create_tweet(text=tweet2, in_reply_to_tweet_id=first_id)
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] 投稿完了 → {first_id}")

# ── 4. メイン ───────────────────────────────
if __name__ == "__main__":
    t1, t2 = make_thread()
    print("------ tweet #1 ------\n" + t1)
    print("------ tweet #2 ------\n" + t2)
    post_thread(t1, t2)
