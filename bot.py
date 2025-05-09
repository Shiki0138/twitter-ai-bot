# bot.py — ChatGPTだけでローカルビジネス向けスレッドを自動投稿
# -------------------------------------------------------------
# ▸ 機能
#   1. ChatGPTに“Tweet1: …\nTweet2: …(\nTweet3: …)”形式で生成させる
#   2. 1ツイート280字を超えたら自動でカット（末尾に … を付与）
#   3. 先頭ツイートを投稿 → 戻り値tweet_idを取得 → 返信で2本目以降を投稿
#   4. 投稿後にタイトル行をログファイルに残し、重複を簡易チェック（同日内のみ）
#
# ▸ 使い方
#   GitHub Actions などで 1 日 5 回このスクリプトを実行 ⇒ 合計 10〜15ツイート
#   （cron は 0 0,4,8,12,16 * * * など UTCベースで設定）
# -------------------------------------------------------------

import os, random, re, hashlib, csv, pathlib, openai, tweepy
from datetime import datetime
from textwrap import shorten
from dotenv import load_dotenv

# ── 環境変数 ───────────────────────────────────────────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
API_KEY        = os.getenv("API_KEY")
API_SECRET     = os.getenv("API_SECRET")
ACCESS_TOKEN   = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET  = os.getenv("ACCESS_SECRET")

# ── 設定 ───────────────────────────────────────────────
LOG_PATH = pathlib.Path("tweet_log.csv")
LOG_PATH.touch(exist_ok=True)

TEMPLATES = [
    "質問フック型", "事例インパクト型", "課題→手順型", "ミニストーリー型"
]
TARGETS = [
    "美容室", "歯科医院", "士業(税理士や社労士)", "コーヒーショップ",
    "ヨガインストラクター", "学習塾", "写真スタジオ"
]

# ── 生成プロンプト作成 ───────────────────────────────
PROMPT_BASE = (
    "あなたはSNSマーケコンサルタントです。対象はローカルビジネス経営者やフリーランス。\n"
    "ChatGPTの便利ワザをわかりやすく紹介するスレッドを作ります。\n"
    "■条件\n"
    "- 日本語、カジュアル丁寧、絵文字は多用しない\n"
    "- Tweet1 は興味を引く導入、Tweet2 以降で具体テクニックを1つ解説\n"
    "- 140字以内/ツイート、改行は2回まで可、引用符やJSONは使わない\n"
    "- 最後のツイートで行動を促す\n"
    "- 3ツイート目は必要なときのみ"
)

# ── 重複チェック（同日）────────────────────────────

def is_today_duplicate(title_line: str) -> bool:
    today = datetime.now().strftime("%Y-%m-%d")
    with LOG_PATH.open() as f:
        return any(row and row[0] == today and row[1] == title_line for row in csv.reader(f))


def log_title(title_line: str):
    today = datetime.now().strftime("%Y-%m-%d")
    with LOG_PATH.open("a", newline="") as f:
        csv.writer(f).writerow([today, title_line])

# ── ChatGPTからスレッド生成 ───────────────────────────

def generate_thread() -> list[str]:
    template = random.choice(TEMPLATES)
    target   = random.choice(TARGETS)
    title    = f"{template}:{target}"

    if is_today_duplicate(title):
        # 乱数で再生成
        return generate_thread()

    prompt = (
        PROMPT_BASE +
        f"\n\n■今回のテンプレート: {template}\n■対象業種: {target}\n"
    )

    rsp = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=220,
        temperature=0.9,
        frequency_penalty=0.4,
    )

    raw = rsp.choices[0].message.content.strip()
    tweets = []
    for line in raw.split("\n"):
        if line.startswith("Tweet"):
            txt = re.sub(r"^Tweet\d+:\s*", "", line).strip()
            if txt:
                tweets.append(shorten(txt, width=279, placeholder="…"))
    if len(tweets) < 2:
        raise ValueError("生成ツイートが不足しました")

    log_title(title)
    return tweets

# ── 投稿処理 ──────────────────────────────────────────

def post_thread(tweets: list[str]):
    client = tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_SECRET,
    )

    # 1ツイート目
    first = client.create_tweet(text=tweets[0])
    reply_to = first.data.get("id")

    # 2ツイート目以降
    for txt in tweets[1:]:
        res = client.create_tweet(text=txt, in_reply_to_tweet_id=reply_to)
        reply_to = res.data.get("id")

    print(f"{len(tweets)} tweets posted at", datetime.now())

# ── メイン ──────────────────────────────────────────
if __name__ == "__main__":
    thread = generate_thread()
    post_thread(thread)
