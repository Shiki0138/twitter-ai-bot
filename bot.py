###############################################
# bot.py — Sheets→GPT→X 自動投稿 1日3回版
# テーマ限定 & 共感/驚きフック（2025‑05‑18 修正版）
###############################################

import os, re, json, datetime, textwrap, random
from typing import List

import tweepy, openai, gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# ── 環境変数 ────────────────────────────────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
API_KEY        = os.getenv("API_KEY")
API_SECRET     = os.getenv("API_SECRET")
ACCESS_TOKEN   = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET  = os.getenv("ACCESS_SECRET")
SHEET_URL      = os.getenv("SHEET_URL")
SERVICE_JSON   = os.getenv("GOOGLE_SERVICE_JSON")

# ── Twitter クライアント ───────────────────
client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET,
    wait_on_rate_limit=True,
)

# ── Google Sheets クライアント ──────────────
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
if os.path.isfile(str(SERVICE_JSON)):
    creds = Credentials.from_service_account_file(SERVICE_JSON, scopes=SCOPES)
else:
    creds = Credentials.from_service_account_info(json.loads(SERVICE_JSON), scopes=SCOPES)

gc = gspread.authorize(creds)
sheet = gc.open_by_url(SHEET_URL).sheet1

# ── 制限テーマ ──────────────────────────────
THEMES = [
    "美容師のインスタ集客",
    "美容師の集客",
    "美容師の経営戦略",
    "美容室経営者向け情報",
    "美容師の生成AI活用",
]
THEME_REGEX = re.compile("|".join(re.escape(t) for t in THEMES))
EMOJIS = ["🎯", "💡", "✨", "📈", "🚀"]

# ── GPT プロンプト ─────────────────────────
SYS_EXTRACT = (
    "あなたは美容師・美容室オーナー専門のコンサルタント兼コピーライターです。\n"
    "入力文から、美容師が\"共感\"または\"驚き\"を感じる要点を1文に要約してください。"
)

SYS_TWEET = (
    "以下の要点をもとに、美容師向け X(Twitter) 投稿文を作成してください。\n"
    "◆ 1ツイート140文字以内。超える場合は<split>タグで分割。\n"
    "◆ 1ツイート目は共感フックか驚き統計で始める。\n"
    "◆ 絵文字は {emoji} を文中か末尾に1個だけ使う。\n"
    "◆ ハッシュタグは一切付けない。\n"
    "◆ 読んだ瞬間にシェアしたくなるように洞察・具体例を入れる。"
)

MODEL = "gpt-4o-mini"
RE_SPLIT = re.compile(r"<split>")
MAX_LEN = 140

# ── GPT ヘルパー ─────────────────────────

def extract_useful(raw: str) -> str:
    res = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYS_EXTRACT},
            {"role": "user", "content": raw},
        ],
    )
    return res.choices[0].message.content.strip()


def make_tweets(useful: str) -> List[str]:
    prompt = SYS_TWEET.format(emoji=random.choice(EMOJIS))
    res = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": useful},
        ],
    ).choices[0].message.content.strip()

    parts = [p.strip() for p in RE_SPLIT.split(res) if p.strip()]

    fixed: List[str] = []
    for p in parts:
        if len(p) <= MAX_LEN:
            fixed.append(p)
        else:
            fixed.extend(textwrap.wrap(p, MAX_LEN - 1))
    return fixed

# ── Twitter 投稿 ───────────────────────────

def post_thread(texts: List[str]) -> None:
    root = client.create_tweet(text=texts[0])
    reply_to = root.data["id"]
    for t in texts[1:]:
        tw = client.create_tweet(text=t, in_reply_to_tweet_id=reply_to)
        reply_to = tw.data["id"]

# ── メイン処理 ────────────────────────────

def process_one_row() -> None:
    rows = sheet.get_all_records()
    for idx, row in enumerate(rows, start=2):
        if row.get("Posted"):
            continue
        raw_text = row.get("抽出テキスト", "").strip()
        if not raw_text:
            continue
        # テーマ判定（キーワード一致 & GPT 判定）
        if not THEME_REGEX.search(raw_text):
            continue  # テーマ外はスキップ

        useful = row.get("UsefulInfo") or extract_useful(raw_text)
        tweets = json.loads(row.get("TweetsJSON") or "[]") or make_tweets(useful)

        post_thread(tweets)

        sheet.batch_update([
            {"range": f"D{idx}", "values": [[useful]]},
            {"range": f"E{idx}", "values": [[json.dumps(tweets, ensure_ascii=False)]]},
            {"range": f"F{idx}", "values": [[True]]},
            {"range": f"G{idx}", "values": [[datetime.datetime.now().isoformat()]]},
        ])
        print(f"✅ Posted row {idx}")
        return
    print("🚫 No unposted rows found or no rows match themes.")


if __name__ == "__main__":
    process_one_row()
