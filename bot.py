# bot.py — UTF-8 safe & 1st tweet 120文字＋改行仕様
# ============================================================
# ライブラリ: openai>=1.3.0, tweepy>=4.14.0, python-dotenv>=1.0.1

import os, re, random, time, hashlib, datetime, unicodedata
import openai, tweepy
from pathlib import Path
from dotenv import load_dotenv

# ────────────────────── 設定 ───────────────────────────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

API_KEY        = os.getenv("API_KEY")
API_SECRET     = os.getenv("API_SECRET")
ACCESS_TOKEN   = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET  = os.getenv("ACCESS_SECRET")

LOG_DIR = Path("tweet_logs")
LOG_DIR.mkdir(exist_ok=True)

TEMPLATES = [
    "質問フック型", "驚き事例型", "課題解決ステップ型", "ストーリー共感型"
]

PROMPT_CORE = (
    "あなたはSNSマーケティングのプロです。ローカルビジネス経営者やフリーランスに向けて、ChatGPT活用の小ネタを日本語で紹介してください。\n"
    "出力は必ず次の形式で:\nTweet1: ……\nTweet2: …… (必要なら Tweet3: …)\n"
    "Tweet1 は120文字以内・改行1回入り。Tweet2 以降は箇条書き可。\n"
    "口調はカジュアル。具体例や数字を入れ、最後に行動を促す。"
)

# ────────────────── ユーティリティ ────────────────────

def _clean(text: str) -> str:
    """サロゲート残りや制御文字を除去してUTF-8セーフに"""
    text = unicodedata.normalize("NFC", text)
    return text.encode("utf-8", "ignore").decode("utf-8", "ignore")


def _insert_break(text: str, limit: int = 120) -> str:
    """120文字以内に収めつつ自然な改行を1つ挿入"""
    txt = text.strip()[:limit]
    if len(txt) <= 60:
        return txt
    # 句読点優先
    for mark in "。!?！？」":
        pos = txt.find(mark, 50, 110)
        if pos != -1:
            return txt[: pos + 1] + "\n" + txt[pos + 1 :]
    mid = len(txt) // 2
    return txt[:mid] + "\n" + txt[mid:]


def generate_thread() -> list[str]:
    template = random.choice(TEMPLATES)
    prompt = f"{PROMPT_CORE}\n# テンプレート: {template}"
    rsp = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.9,
    )
    raw = _clean(rsp.choices[0].message.content)
    parts = re.findall(r"Tweet\d+:\s*(.+)", raw, flags=re.I)
    if not parts:
        # 改行区切り fallback
        parts = [p.strip() for p in raw.split("\n") if p.strip()]
    if not parts:
        raise ValueError("生成ツイートが不足しました")
    # 1本しかない場合は強制分割
    if len(parts) == 1:
        first = _insert_break(parts[0])
        parts = [first] + [parts[0][len(first):].lstrip()]
    # 先頭ツイート調整
    parts[0] = _insert_break(parts[0])
    # 280字制限
    parts = [p[:279] + ("…" if len(p) > 279 else "") for p in parts]
    return parts[:3]


def post_thread(parts: list[str]):
    client = tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_SECRET,
    )
    head = client.create_tweet(text=parts[0])
    head_id = head.data.get("id")
    print("Tweeted:", parts[0])
    for body in parts[1:]:
        time.sleep(2)
        client.create_tweet(text=body, in_reply_to_tweet_id=head_id)
        print("→ replied:", body)


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

# ────────────────────────── main ───────────────────────────

def main():
    parts = generate_thread()
    if is_duplicate(parts[0]):
        print("Duplicate detected. Skip posting.")
        return
    post_thread(parts)

if __name__ == "__main__":
    main()
