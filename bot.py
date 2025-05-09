# bot.py — GPT-4o-mini版：数字・事例・驚きを必ず含む「1 〜 3 ツイート」自動投稿
# =====================================================================
# requirements.txt
#   openai>=1.3.0         (GPT-4o-mini 対応クライアント)
#   tweepy>=4.14.0
#   python-dotenv>=1.0.1
#
# 特徴
#   ● ChatGPT (gpt-4o-mini) でスレッド生成
#   ● Tweet1 が 100-140 字かつ「数字 × 驚き語(!/驚/衝撃)」必須
#   ● Tweet1 が <110 字なら Tweet2/3 を改行で結合 → 単発ツイート化
#   ● 110 字以上なら 2 ～ 3 本を reply チェーンで投稿
#   ● 先頭条件 NG → 最大 5 回リトライ → フォールバックしてでも投稿
#   ● UTF-8 セーフ、280 字制限、同日重複防止ログ
# ---------------------------------------------------------------------

import os
import re
import random
import time
import hashlib
import datetime
import unicodedata
from pathlib import Path

import openai
import tweepy
from dotenv import load_dotenv

# ───────────────────  環境変数  ────────────────────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

API_KEY       = os.getenv("API_KEY")
API_SECRET    = os.getenv("API_SECRET")
ACCESS_TOKEN  = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("ACCESS_SECRET")

client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET,
)

# ───────────────────  ログ保存  ────────────────────
LOG_DIR = Path("tweet_logs")
LOG_DIR.mkdir(exist_ok=True)

def _hash_today(txt: str) -> str:
    today = datetime.date.today().isoformat()
    return hashlib.md5((today + txt).encode()).hexdigest()

def is_duplicate(txt: str) -> bool:
    h = _hash_today(txt)
    log_file = LOG_DIR / f"{datetime.date.today():%Y%m%d}.log"
    if log_file.exists() and h in log_file.read_text().split():
        return True
    log_file.write_text((log_file.read_text() if log_file.exists() else "") + h + "\n")
    return False

# ───────────────────  生成用データ  ──────────────────
TEMPLATES = [
    "質問フック型", "驚き事例型", "課題解決ステップ型", "ストーリー共感型"
]

STAT_POOL = [
    "米国中小企業の83%がAIで業務効率化を実感（BPC調査）",
    "パナソニックコネクトは社内ChatGPTで18.6万時間削減",
    "企業の生成AI導入トップ用途はコンテンツ作成49.4%",
    "ChatGPT導入で顧客対応解決率60%向上（米調査）",
]

FACT_POOL = [
    "ロンドン美容室BleachはAI活用SNSで新規予約20%増",
    "北海道の歯科医院スマイルデンタルはAIリマインドで無断キャンセル45%減",
    "NYのパーソナルジムはAIアンケ分析でクロージング率+18%",
    "名古屋の社労士事務所はChatGPTで就業規則ドラフトを1日→30分に短縮",
    "大阪の個人パン屋は日替りメニュー案をAIで生成し売上14%UP",
    "ベルリンのヘアサロンはAI自動DMで直前空き枠85%回収",
    "横浜のコーチ業は提案書アイデア出しをAIに依頼し作成時間70%短縮",
    "ロサンゼルスのカフェはAIによる口コミ返信で評価★4.3→4.7",
    "シンガポールの法務コンサルは契約書チェックをAI補助し工数半減",
    "福岡のネイルサロンはAI画像キャプション活用でInstagramリーチ3倍",
    "ソウルの動物病院はAI FAQチャットで電話問い合わせ23%削減",
    "パリの語学スクールはAI教材生成で講師準備時間40%圧縮"
]

# ───────────────────  パラメータ  ───────────────────
MODEL_NAME  = "gpt-4o-mini"
TEMP        = 1.2
TOP_P       = 1
MAX_TOKENS  = 350
MIN_LEN     = 100       # 先頭ツイ最低
MAX_LEN     = 140
THRESH      = 110       # これ未満なら単発化

RE_SURPRISE = re.compile(r"[!！]|驚|衝撃")

# ───────────────────  ユーティリティ  ──────────────
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
            return text[: pos + 1] + "\n" + text[pos + 1 :]
    mid = limit
    return text[:mid] + "\n" + text[mid:]

def _parse(raw: str) -> list[str]:
    parts = re.findall(r"Tweet\\d+:\\s*(.+)", raw, flags=re.I)
    if not parts:
        parts = [p.strip() for p in raw.split("\n") if p.strip()]
    return parts

def valid_first(t: str) -> bool:
    return (MIN_LEN <= len(t) <= MAX_LEN) and RE_SURPRISE.search(t) and re.search(r"\d", t)

# ───────────────────  生成  ──────────────────────────
def generate_thread() -> list[str]:
    template = random.choice(TEMPLATES)
    stat     = random.choice(STAT_POOL)
    fact     = random.choice(FACT_POOL)

    PROMPT = (
        f"あなたはSNSマーケター兼リサーチャーです。"
        f"以下の統計と事例を必ず引用して、ローカルビジネス向けChatGPT活用法を作成してください。\n"
        f"統計: {stat}\n"
        f"事例: {fact}\n"
        "出力は必ず次の形式:\n"
        "Tweet1: …\nTweet2: …\nTweet3: …（必要なら）\n"
        "Tweet1は100–140字で1回改行を含み、数字と驚き語(!/驚/衝撃)を必ず入れる。\n"
        "Tweet2/3は120–140字、ROIや行動促進を明確に。\n"
        "テンプレート: " + template
    )

    for _ in range(5):
        rsp = openai.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": PROMPT}],
            max_tokens=MAX_TOKENS,
            temperature=TEMP,
            top_p=TOP_P,
        )
        raw    = _clean(rsp.choices[0].message.content)
        parts  = _parse(raw)
        if len(parts) < 2:
            continue
        parts[0] = _insert_break(parts[0])
        if valid_first(parts[0]):
            break
    else:
        # フォールバック: 制約緩和
        rsp = openai.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": PROMPT.replace("100–140", "90–140")}],
            max_tokens=MAX_TOKENS,
            temperature=TEMP,
            top_p=TOP_P,
        )
        parts = _parse(_clean(rsp.choices[0].message.content))

    if not parts:
        raise RuntimeError("ChatGPTからツイートを取得できませんでした")

    # 1本しか無ければ強制分割
    if len(parts) == 1:
        txt = parts[0]
        cut = max(60, len(txt) // 2)
        parts = [txt[:cut], txt[cut:]]

    # 長さトリム
    trimmed = []
    for p in parts[:3]:
        p = p.strip()
        if len(p) > MAX_LEN:
            p = p[:MAX_LEN - 1] + "…"
        trimmed.append(p)

    return [_clean(t) for t in trimmed if t.strip()]

# ───────────────────  投稿  ──────────────────────────
def post(parts: list[str]):
    if len(parts) >= 2 and len(parts[0]) < THRESH:
        # 先頭が短い → 単発ツイートにまとめる
        single = parts[0] + "\n\n" + "\n\n".join(parts[1:])
        single = single[:279] + ("…" if len(single) > 279 else "")
        client.create_tweet(text=single)
        print("Tweeted (single):", single[:60], "…")
        return

    # スレッド投稿
    head_id = client.create_tweet(text=parts[0]).data["id"]
    print("Tweeted:", parts[0])
    prev_id = head_id

    for body in parts[1:]:
        time.sleep(2)
        body = body.strip()
        if not body:           # 万一空文字ならスキップ
            continue
        prev_id = client.create_tweet(text=body, in_reply_to_tweet_id=prev_id).data["id"]
        print(" replied:", body[:40], "...")

# ───────────────────  main  ──────────────────────────
def main():
    parts = generate_thread()
    if is_duplicate(parts[0]):
        print("Duplicate detected. skip.")
        return
    try:
        post(parts)
    except Exception as e:
        print("⚠️ thread post failed:", e)
        # フォールバック：先頭だけでも投稿
        client.create_tweet(text=parts[0][:MAX_LEN])
        print("Posted head only.")

if __name__ == "__main__":
    main()
