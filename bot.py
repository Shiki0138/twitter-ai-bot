# bot.py — 120〜140字×最大3ツイートの“情報濃いスレッド”専用
# ============================================================
#   • Tweet1  : インパクトある統計・数字・疑問形など(120‑140字)
#   • Tweet2  : 丁寧な解説(120‑140字)
#   • Tweet3* : さらに深掘り or 行動促進(120‑140字) ※必須ではない
#   • 先頭ツイートが必ず 120字以上＆情報フックを含むまで再生成リトライ
#   • 空ツイート・140字超は自動カット/リジェネ
# -------------------------------------------------------------
# requirements.txt
#   openai>=1.3.0
#   tweepy>=4.14.0
#   python-dotenv>=1.0.1
# -------------------------------------------------------------

import os, re, random, time, hashlib, datetime, unicodedata, textwrap
from pathlib import Path

import openai, tweepy
from dotenv import load_dotenv

# ─── 環境変数 ───────────────────────────────────────────
load_dotenv()
openai.api_key  = os.getenv("OPENAI_API_KEY")
API_KEY         = os.getenv("API_KEY")
API_SECRET      = os.getenv("API_SECRET")
ACCESS_TOKEN    = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET   = os.getenv("ACCESS_SECRET")

# ─── Tweepy Client ──────────────────────────────────────
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET,
)

# ─── 定数 ─────────────────────────────────────────────
LOG_DIR = Path("tweet_logs"); LOG_DIR.mkdir(exist_ok=True)
MIN_LEN, MAX_LEN = 120, 140

PROMPT = textwrap.dedent("""
あなたはSNSマーケティングのプロです。ローカルビジネス経営者やフリーランス（美容師・歯科医師・小売店・士業など）に向けて、ChatGPT活用の最新テクニックを紹介します。
- 出力は必ず以下の書式:
Tweet1: …(120~140字)
Tweet2: …(120~140字)
Tweet3(任意): …(120~140字)
- Tweet1 は驚きの数字や質問形などで強いフックを作る。
- Tweet2・3 で丁寧に手順やメリットを解説し、最後は行動を促す。
- すべて自然な日本語。専門用語はかみくだき、改行は最大1回まで。
- ChatGPT以外のツール名は出さない。
""")

TWEET_RE = re.compile(r"Tweet\d+:\s*(.+)", re.I)

# ─── ユーティリティ ───────────────────────────────

def _clean(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    return text.encode("utf-8", "ignore").decode("utf-8", "ignore")

def _length_ok(t: str) -> bool:
    L = len(t)
    return MIN_LEN <= L <= MAX_LEN

def _hash_today(text: str) -> str:
    today = datetime.date.today().isoformat()
    return hashlib.md5((today + text).encode()).hexdigest()

def is_duplicate(text: str) -> bool:
    h = _hash_today(text)
    f = LOG_DIR / f"{datetime.date.today():%Y%m%d}.log"
    if f.exists() and h in f.read_text().split():
        return True
    f.write_text((f.read_text() if f.exists() else "") + h + "\n")
    return False

# ─── 生成 ────────────────────────────────────────────

def generate_thread(max_retry=4) -> list[str]:
    for _ in range(max_retry):
        rsp = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": PROMPT}],
            max_tokens=320,
            temperature=0.9,
        )
        raw = _clean(rsp.choices[0].message.content)
        parts = TWEET_RE.findall(raw)
        if not parts:
            parts = [t.strip() for t in raw.split("\n") if t.strip()]
        parts = [_clean(p)[:MAX_LEN] for p in parts if _length_ok(p[:MAX_LEN])]
        if len(parts) >= 2 and _length_ok(parts[0]):
            return parts[:3]
    raise RuntimeError("ツイート生成に失敗しました")

# ─── 投稿 ────────────────────────────────────────────

def post_thread(parts: list[str]):
    head_id = client.create_tweet(text=parts[0]).data["id"]
    print("Posted:", parts[0])
    for body in parts[1:]:
        time.sleep(2)
        client.create_tweet(text=body, in_reply_to_tweet_id=head_id)
        print(" → replied:", body[:60])

# ─── main ──────────────────────────────────────────────

def main():
    parts = generate_thread()
    if is_duplicate(parts[0]):
        print("Duplicate detected – skip.")
        return
    post_thread(parts)

if __name__ == "__main__":
    main()
