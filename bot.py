# bot.py — ChatGPT だけで 1 日 5 スレッド（計 10 ツイート）投稿
# -------------------------------------------------------------
# 必要ライブラリ（requirements.txt に書く）：
#   openai>=1.3.0
#   tweepy>=4.14.0
#   python-dotenv>=1.0.1
# -------------------------------------------------------------

import os, json, random, time, openai, tweepy
from datetime import datetime
from dotenv import load_dotenv

# ── 0. 環境変数読み込み ───────────────────────────────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

API_KEY        = os.getenv("API_KEY")
API_SECRET     = os.getenv("API_SECRET")
ACCESS_TOKEN   = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET  = os.getenv("ACCESS_SECRET")

if not all([openai.api_key, API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET]):
    raise RuntimeError("環境変数が不足しています .env を確認してください")

# ── 1. 投稿テーマ候補（必要に応じて増やす） ─────────────
TOPICS = [
    "美容室のSNSネタ自動生成",
    "予約リマインドの自動作成",
    "朝礼ネタのクイズ化",
    "アンケート自動分析",
    "ChatGPT便利ネタ",
]

# ── 2. GPT へ渡す共通プロンプト ────────────────────
SYSTEM_PROMPT = (
    "あなたは地方の美容室や歯科医院などローカルビジネスの\n"
    "経営者向けSNSライターです。\n"
    "驚きと実用性を両立した生成AI(ChatGPT)活用テクニックを\n"
    "日本語140字以内で 2 本のツイート(スレッド)にまとめます。\n"
    "1本目: 興味を引く導入。\n"
    "2本目: 具体的手順を5行程度で。\n"
    "共通のルール:\n"
    "・句読点を含め140文字以内\n"
    "・『▼詳細はリプ欄』などのCTAは入れない\n"
    "・絵文字は使用しない\n"
    "JSON 形式 {\"first\": .., \"second\": ..} だけを出力してください。"
)

# ── 3. GPT から 2 本のツイート文を取得 ───────────────

def generate_thread(topic: str) -> tuple[str, str]:
    """ChatGPT で (first, second) 2 つのツイートを生成"""
    user_prompt = f"トピック: {topic}"
    rsp = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=200,
        temperature=0.9,
    )
    content = rsp.choices[0].message.content.strip()
    try:
        data = json.loads(content)
        return data["first"], data["second"]
    except Exception as e:
        # 失敗時はプレーンテキストを分割して返す
        parts = content.split("\n", 1)
        return parts[0][:140], (parts[1] if len(parts) > 1 else "続きはコメントへ")[:140]

# ── 4. ツイート投稿 ─────────────────────────────

def post_thread(first: str, second: str):
    client = tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_SECRET,
    )
    # 1 本目
    response = client.create_tweet(text=first)
    tweet_id = response.data.get("id")
    print("Tweeted 1/2 →", tweet_id)
    # X API の write 制限対策で 3 秒待機
    time.sleep(3)
    # 2 本目（リプライ）
    client.create_tweet(text=second, in_reply_to_tweet_id=tweet_id)
    print("Tweeted 2/2 → reply to", tweet_id)

# ── 5. main: 1 スレッドだけ投稿する ─────────────────
if __name__ == "__main__":
    topic = random.choice(TOPICS)
    print("▶ 選択トピック:", topic)
    first, second = generate_thread(topic)
    print("▶ 生成文\n1:", first, "\n2:", second)
    post_thread(first, second)
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] 完了")
