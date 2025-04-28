import os
print("OPENAI key length:", len(os.getenv("OPENAI_API_KEY") or "0"))
import os, random, tweepy, openai
from datetime import datetime
from dotenv import load_dotenv

from dotenv import load_dotenv
load_dotenv(override=False)

OPENAI_KEY   = os.getenv("OPENAI_API_KEY")
API_KEY      = os.getenv("API_KEY")
API_SECRET   = os.getenv("API_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET= os.getenv("ACCESS_SECRET")

TOPICS = [
    "海外の中小企業が生成AIで劇的コスト削減した話",
    "国内ベンチャーがChatGPTで売上2倍にした裏側",
    "AI × 観光で口コミ爆増したホテルの事例",
    "生成AIで業務マニュアルが10分で完成した方法"
]

def make_tweet():
    print("▶ make_tweet() 開始")
    topic = random.choice(TOPICS)

    prompt = (
        "あなたは日本の経営者に向けて、生成AI活用の面白い事例を140字以内で紹介します。"
        "1) 数字でインパクト 2) わかりやすく 3) 最後に『▼詳細はリプ欄』CTA。"
        f" トピック: {topic}"
    )

    openai.api_key = OPENAI_KEY

    res = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=120,
        temperature=0.7,
        frequency_penalty=0.2,
    )

    return res.choices[0].message.content.strip()[:140]


# === post() : Twitter API v2 専用 ===
def post(tweet):
    print("▶ post() 送信直前")            # ← 追加
    client = tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_SECRET,
    )
    response = client.create_tweet(text=tweet)
    print("▶ post() 応答:", response)      # ← 追加
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] 投稿完了 (v2)")
# ====================================

# ====== main 実行部 ======
if __name__ == "__main__":
    print("▶ main 開始")
    post(make_tweet())
# =========================
