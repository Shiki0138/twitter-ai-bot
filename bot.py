# bot.py — ChatGPTだけでローカルビジネス向けスレッドを自動投稿
# ============================================================
# 概要
#   • ChatGPT (openai>=1.3.0) にプロンプトを送り、Tweet1: / Tweet2: 形式で
#     1スレッド(2〜3ツイート) を生成。
#   • 先頭ツイートを投稿し、その tweet_id にセルフリプライして続ける。
#   • 同一日のネタ被りを避けるためタイトルを簡易ハッシュしてログ保存。
#   • GitHub Actions で 1 日 5 回実行すれば月間 150 スレッド＝約 450 ツイート。
# ------------------------------------------------------------
# 必要ライブラリ   : openai>=1.3.0, tweepy>=4.14.0, python-dotenv>=1.0.1
# 環境変数 (Secrets): OPENAI_API_KEY, API_KEY, API_SECRET,
#                     ACCESS_TOKEN, ACCESS_SECRET
# ------------------------------------------------------------

import os, re, random, csv, pathlib, openai, tweepy
from datetime import datetime
from dotenv import load_dotenv

# ── 0. 環境読み込み ─────────────────────────────────────────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

API_KEY        = os.getenv("API_KEY")
API_SECRET     = os.getenv("API_SECRET")
ACCESS_TOKEN   = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET  = os.getenv("ACCESS_SECRET")

# ── 1. 投稿テンプレート ───────────────────────────────────
TEMPLATES = [
    "質問フック型: まだ◯◯に時間を浪費していませんか？→",
    "驚き事例型: ChatGPTで△△が30秒!?→",
    "課題解決ステップ型: 顧客対応ストレスを3STEPで削減→",
    "ストーリー共感型: 昨日こんな相談を受けました→"
]

PROMPT_CORE = (
    "あなたはSNSマーケティングのプロです。ローカルビジネス経営者・フリーランスが\n"
    "\uD83D\uDE4C『え! 面白そう、やってみたい』と思うChatGPT活用法を紹介します。\n"
    "必ず下記フォーマットで出力してください。\n\n"
    "Tweet1: 導入(120字程度)\n"
    "Tweet2: アイデア詳細(改行込み140字以内)\n"
    "Tweet3: 行動呼びかけ(任意・120字以内)\n"
    "— 注意 —\n"
    "* それぞれ140字以内、日本語、自然な改行(空行2回も可)。\n"
    "* ダブルクォーテーション \"\" は使わない。\n"
    "* 専門用語は噛み砕いて。\n"
    "* ChatGPT以外のツール名は出さない。\n"
)

# ── 2. GPT呼び出し & 分割 ────────────────────────────────

def build_prompt() -> str:
    return PROMPT_CORE + "\n導入テンプレート例: " + random.choice(TEMPLATES)


def call_gpt(prompt: str) -> str:
    rsp = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=350,
        temperature=0.9,
        frequency_penalty=0.4,
    )
    return rsp.choices[0].message.content.strip()


def split_tweets(text: str) -> list[str]:
    """Tweet1:〜 の書式を抜き出し、なければfallbackとして空行2連で区切る"""
    parts = re.findall(r"Tweet\d+:\s*(.+)", text, flags=re.I | re.S)
    if not parts:
        parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(parts) == 1:  # 保険: 1本しか無いなら 50/50 で分割
        half = len(parts[0]) // 2
        parts = [parts[0][:half], parts[0][half:]]
    trimmed = []
    for p in parts:
        p = p.replace("\r", "").strip()
        if len(p) > 280:
            p = p[:277] + "…"
        trimmed.append(p)
    return trimmed[:3]  # Max 3本

# ── 3. 重複チェック用ログ ───────────────────────────────
LOG_DIR = pathlib.Path("tweet_logs")
LOG_DIR.mkdir(exist_ok=True)


def posted_today(headline: str) -> bool:
    log = LOG_DIR / f"{datetime.now():%Y%m%d}.csv"
    if not log.exists():
        return False
    with log.open() as f:
        return any(headline[:50] == row[0] for row in csv.reader(f))


def append_log(headline: str):
    log = LOG_DIR / f"{datetime.now():%Y%m%d}.csv"
    with log.open("a", newline="") as f:
        csv.writer(f).writerow([headline[:50], datetime.now().isoformat()])

# ── 4. スレッド生成 ──────────────────────────────────────

def generate_thread() -> list[str]:
    for _ in range(4):  # 4回までリトライ
        prompt = build_prompt()
        output = call_gpt(prompt)
        parts = split_tweets(output)
        if len(parts) >= 2 and not posted_today(parts[0]):
            return parts
    raise ValueError("生成ツイートが不足しました")

# ── 5. 送信 ─────────────────────────────────────────────

def post_thread(parts: list[str]):
    client = tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_SECRET,
    )
    first = client.create_tweet(text=parts[0])
    tweet_id = first.data["id"]
    for p in parts[1:]:
        resp = client.create_tweet(text=p, in_reply_to_tweet_id=tweet_id)
        tweet_id = resp.data["id"]
        time.sleep(1)  # API節度
    append_log(parts[0])
    print("Posted thread:", parts[0][:60])

# ── 6. メイン ───────────────────────────────────────────
if __name__ == "__main__":
    try:
        thread = generate_thread()
        post_thread(thread)
    except Exception as e:
        print("❌", e)
