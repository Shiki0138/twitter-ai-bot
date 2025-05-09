# bot.py — ChatGPTだけでローカルビジネス向けスレッドを自動投稿（UTF-8安全版）
# ============================================================
# * GitHub Actions で 1 日 5 回実行 → 月間 150 スレッド ≈ 450 ツイート
# * ChatGPT から "Tweet1:" "Tweet2:" … を生成して投稿
# * サロゲート残りで "utf-8 codec can't encode" が出ないよう、
#   すべてのテキストを UTF-8 セーフにクレンジングしてから print / 投稿
# -------------------------------------------------------------
# requirements.txt
#   openai>=1.3.0
#   tweepy>=4.14.0
#   python-dotenv>=1.0.1
# -------------------------------------------------------------

import os, re, random, hashlib, datetime, openai, tweepy
from pathlib import Path
from dotenv import load_dotenv

# ── 0. 環境変数 ─────────────────────────────────────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
API_KEY        = os.getenv("API_KEY")
API_SECRET     = os.getenv("API_SECRET")
ACCESS_TOKEN   = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET  = os.getenv("ACCESS_SECRET")

# ── 1. UTF‑8 セーフにするユーティリティ ───────────────

def clean_utf8(text: str) -> str:
    """サロゲート片割れ・制御文字を除去し、UTF‑8 で確実に出力できる形に"""
    text = ''.join(ch for ch in text if not 0xD800 <= ord(ch) <= 0xDFFF)
    return text.encode('utf-8', 'ignore').decode('utf-8', 'ignore')

# ── 2. プロンプトテンプレート ───────────────────────
TEMPLATES = [
    """あなたはSNSマーケのプロです。ローカルビジネス経営者やフリーランスに向け、ChatGPT活用ネタをXで紹介します。必ず以下形式で出力してください：\nTweet1: 読者の興味を引く導入文（80〜100字）\nTweet2: ChatGPT活用テクニックの本編（120字以内）\nTweet3: 行動を促す締め（質問・CTAを含む、80字以内）""",
    """あなたは生成AIエバンジェリスト。中小事業主が「試したくなる」ChatGPTワザを教えてください。形式は：\nTweet1: つかみ 90字以内\nTweet2: 具体ステップ 箇条書きOK 120字以内\nTweet3: 締め 80字以内""",
]

REGEX_SPLIT = re.compile(r"Tweet\d+:\s*(.+)", re.I)

# ── 3. ChatGPT からスレッド生成 ───────────────────

def generate_thread() -> list[str]:
    prompt = random.choice(TEMPLATES)
    rsp = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=250,
        temperature=0.9,
    )
    raw = rsp.choices[0].message.content.strip()
    parts = [m.strip() for m in REGEX_SPLIT.findall(raw)]
    if len(parts) < 2:  # フォールバック：改行で分断
        parts = [p.strip() for p in raw.split("\n") if p.strip()]
    if len(parts) == 1:  # 1本しかなければ強制2分割
        text = parts[0]
        midpoint = len(text) // 2
        parts = [text[:midpoint], text[midpoint:]]
    # 280字カット & UTF8 セーフ
    parts = [clean_utf8(p)[:280] + ("…" if len(p) > 280 else "") for p in parts]
    return parts

# ── 4. 同日重複チェック ───────────────────────────
LOG_PATH = Path(f"tweet_log_{datetime.date.today():%Y%m%d}.txt")
LOG_PATH.touch(exist_ok=True)


def already_posted(signature: str) -> bool:
    return signature in LOG_PATH.read_text().splitlines()

def mark_posted(signature: str):
    with LOG_PATH.open("a", encoding="utf-8", errors="ignore") as f:
        f.write(signature + "\n")

# ── 5. ツイート投稿 ───────────────────────────────

def post_thread(parts: list[str]):
    client = tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_SECRET,
    )
    first_id = None
    for idx, text in enumerate(parts):
        if idx == 0:
            resp = client.create_tweet(text=text)
            first_id = resp.data["id"]
            print("Tweeted:", clean_utf8(text))
            time.sleep(2)
        else:
            resp = client.create_tweet(text=text, in_reply_to_tweet_id=first_id)
            print("Reply:", clean_utf8(text))
            time.sleep(2)

# ── 6. メイン処理 ─────────────────────────────────

def main():
    parts = generate_thread()
    sig = hashlib.sha1(parts[0].encode()).hexdigest()[:10]
    if already_posted(sig):
        print("今日すでに同じネタを投稿済み。スキップ")
        return
    post_thread(parts)
    mark_posted(sig)

if __name__ == "__main__":
    main()
