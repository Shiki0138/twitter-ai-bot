# bot.py — GPT‑4o-mini版：数字・事例・驚きを必ず含む濃密スレッド
# ==================================================================
# ライブラリ
#   openai>=1.3.0  (GPT‑4o-mini 対応)
#   tweepy>=4.14.0
#   python-dotenv>=1.0.1

import os, re, random, time, hashlib, datetime, unicodedata
from pathlib import Path

import openai, tweepy
from dotenv import load_dotenv

# ─────────────────── 環境変数 ────────────────────
load_dotenv()
openai.api_key  = os.getenv("OPENAI_API_KEY")
API_KEY         = os.getenv("API_KEY")
API_SECRET      = os.getenv("API_SECRET")
ACCESS_TOKEN    = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET   = os.getenv("ACCESS_SECRET")

client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET,
)

LOG_DIR = Path("tweet_logs"); LOG_DIR.mkdir(exist_ok=True)

# ─────────────────── 参考データ集 ───────────────────
STAT_POOL = [
    "米Bipartisan Policy Center調査: 中小企業の83%がAIで業務効率化を実感",
    "パナソニックコネクト: 内部ChatGPT導入で年間18.6万時間削減＝労務費2.4億円相当",
    "ロンドン美容室Bleach: SNS×AI活用後、新規予約20%増・リピート12%増",
    "米Goodcall導入歯科医院: AI電話で予約取りこぼし30%→5%、売上15%UP",
    "北海道カフェRain: ChatGPT自動メニュー翻訳で訪日客比率9%→23%に急伸",
    "愛知県ネイルサロンlily: ChatGPTのLINE接客ボットで所要時間/日90→15分",
]

CASE_POOL = [
    {
        "hook": "【驚】予約無断キャンセルが半減!!",
        "body": "福岡の美容院AnchorはChatGPTで\"前日確認メッセージ\"を自動生成→送信。\n無断キャンセル率15%→7%に減り、月間売上+28万円。",
        "cta": "あなたも\"今日の予約一覧\"を貼るだけでOK。まず1通試しませんか？ #生成AI活用"
    },
    {
        "hook": "売上 +32% ➜ たった3行のプロンプト",
        "body": "神奈川の歯科 SmileBright はChatGPTで患者教育メールを自動作成し\nホワイトニング成約率が18%→31%にUP。",
        "cta": "\"施術前の不安を解消する文章を300字で\"と頼むだけ。今晩テストしてみましょう！"
    },
    {
        "hook": "資料作成5時間→10分!?",
        "body": "大阪の社労士OfficeLeafは就業規則案をChatGPTドラフト→チェックに変更。\n1案件あたり4h50m短縮=月30h浮き!",
        "cta": "Wordドラフトを丸ごと貼って\"校正して\"と指示するだけで時短。まず小規程から！"
    },
    {
        "hook": "売場POP100枚を30分で量産!",
        "body": "札幌の雑貨店LampはChatGPT+スプレッドシートでPOP文を自動生成。\n店長1人の作業が1日→30分に短縮し、\n季節フェア売上+18%。",
        "cta": "商品名リストを貼って\"購買意欲を刺激する12字キャッチを\"と依頼➡️印刷するだけ。"
    },
]

TEMPLATES = [c["hook"] for c in CASE_POOL]  # ランダムで選ぶ

# ─────────────────── プロンプト ───────────────────
PROMPT_BASE = (
    "あなたはSNSマーケター兼リサーチャーです。ローカルビジネス経営者やフリーランスが\n"
    "『え! 面白そう、やってみたい』と驚き行動するChatGPT活用ネタをXスレッドにします。\n"
    "必須条件:\n"
    "1. Tweet1 は 100〜140字、疑問形 or 数字入りフックを含み、途中1回改行する。\n"
    "2. Tweet2 は 120〜140字、具体事例やROI、手順を示す。\n"
    "3. Tweet3 (任意) は 120〜140字、CTAとハッシュタグ1つ(#生成AI活用)。\n"
    "4. 実在または実在に極めて近い\"海外or国内の小規模事業\"の数字・効果を入れる。\n"
    "5. 出力は必ず\nTweet1: …\nTweet2: …\n(Tweet3: …) の形式。\n"
)

MIN_LEN, MAX_LEN = 100, 140
first_regex = re.compile(r"[0-9％%]|驚|!?！")  # 数字か驚き表現

# ─────────────────── UTILITY ────────────────────
def _clean(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    return text.encode("utf-8", "ignore").decode("utf-8", "ignore")

def _insert_break(text: str, limit: int = 120) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    for mark in "。.!?！？":
        pos = text.rfind(mark, 50, limit)
        if pos != -1:
            return text[: pos + 1] + "\n" + text[pos + 1 :].lstrip()
    mid = limit
    return text[:mid] + "\n" + text[mid:]

def valid_first(t: str) -> bool:
    return MIN_LEN <= len(t) <= MAX_LEN and first_regex.search(t)

# ─────────────────── スレッド生成 ───────────────────

def _parse_tweets(raw: str) -> list[str]:
    parts = re.findall(r"Tweet\d+:\s*(.+)", raw, flags=re.I)
    if not parts:
        parts = [p.strip() for p in raw.split("\n") if p.strip()]
    return parts

def generate_thread() -> list[str]:
    # 統計＋事例をfew-shotとしてコンテキスト
    stat  = random.choice(STAT_POOL)
    case  = random.choice(CASE_POOL)
    prompt = (
        f"{PROMPT_BASE}\n"
        f"参考統計: {stat}\n"
        f"事例サンプル:\n- {case['hook']}\n  {case['body']}"
    )
    for _ in range(5):
        rsp = openai.chat.completions.create(
            model="gpt-4o-mini",
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
        # fallback: 1本でも投稿できる形に
        if not parts:
            parts = [raw.strip()[:MAX_LEN]]

    if len(parts) == 1:
        text = parts[0]
        split = max(60, len(text) // 2)
        parts = [text[:split], text[split:]]

    trimmed = []
    for p in parts[:3]:
        p = p.strip()
        if len(p) > MAX_LEN:
            p = p[:MAX_LEN - 1] + "…"
        trimmed.append(p)
    return [_clean(t) for t in trimmed if t.strip()]

# ─────────────────── 投稿・重複判定 ───────────────────

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
    parts = [p for p in parts if p.strip()]
    head_id = client.create_tweet(text=parts[0]).data["id"]
    print("Tweeted:", parts[0])
    for body in parts[1:]:
        time.sleep(2)
        client.create_tweet(text=body, in_reply_to_tweet_id=head_id)
        print(" replied:", body[:40], "...")

# ───────────────────────── main ────────────────────────────

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
