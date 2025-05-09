# bot.py — 柔軟スレッド：場合によっては1ツイート、最大3連続 reply チェーン
# ====================================================================
# ポイント
#   1. Tweet1 が <110 字なら Tweet2/3 を改行で結合 → 単発ツイート
#   2. 110 字以上なら 2〜3 本のスレッド投稿
#   3. reply チェーンは『先頭 → 2 → 3』と順番に in_reply_to で繋ぐ
#   4. 先頭は必ず数字 or 驚き語(!/驚/衝撃)
#   5. UTF‑8 セーフ & 同日重複防止
# --------------------------------------------------------------------
# requirements.txt
#   openai>=1.3.0 (gpt-4o-mini)
#   tweepy>=4.14.0
#   python-dotenv>=1.0.1

import os, re, random, time, hashlib, datetime, unicodedata
from pathlib import Path

import openai, tweepy
from dotenv import load_dotenv

# ───── 環境変数 ─────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
API_KEY, API_SECRET = os.getenv("API_KEY"), os.getenv("API_SECRET")
ACCESS_TOKEN, ACCESS_SECRET = os.getenv("ACCESS_TOKEN"), os.getenv("ACCESS_SECRET")

client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET,
)

LOG_DIR = Path("tweet_logs"); LOG_DIR.mkdir(exist_ok=True)

# ───── プロンプト ─────
TEMPLATES = [
    "質問フック型", "驚き事例型", "課題解決ステップ型", "ストーリー共感型"
]
PROMPT_CORE = (
    "あなたはSNSマーケター兼リサーチャーです。"
    "ローカルビジネス経営者向けにChatGPTを使った驚きの活用法を投稿します。\n"
    "出力フォーマット:\nTweet1: …\nTweet2: …\nTweet3: … (任意)\n"
    "Tweet1=100‑140字・改行1回・数字 or 驚き語必須。\n"
    "Tweet2/3=120‑140字で事例やROIを具体数字入りで解説→行動促進。"
)
MIN1, MAX1 = 100, 140
check_word = re.compile(r"(\d+%|\d+時間|\d+倍|驚|衝撃|!)")

# ───── ユーティリティ ─────

def _clean(txt: str) -> str:
    return unicodedata.normalize("NFC", txt).encode("utf-8", "ignore").decode("utf-8", "ignore")

def _insert_break(txt: str, lim=120):
    if len(txt) <= lim:
        return txt
    for mk in "。.!?！？":
        p = txt.rfind(mk, 50, lim)
        if p != -1:
            return txt[:p+1]+"\n"+txt[p+1:]
    return txt[:lim]+"\n"+txt[lim:]

def _parse(raw: str):
    parts = re.findall(r"Tweet\d+:\s*(.+)", raw, flags=re.I)
    if not parts:
        parts = [p.strip() for p in raw.split("\n") if p.strip()]
    return parts

def _valid_first(t):
    return MIN1 <= len(t) <= MAX1 and check_word.search(t)

# ───── スレッド生成 ─────

def generate_thread():
    template = random.choice(TEMPLATES)
    for _ in range(5):
        rsp = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system","content":"あなたは信頼できるAI活用アドバイザーです。"},
                {"role":"user","content":f"{PROMPT_CORE}\nテンプレ:{template}"},
            ],
            max_tokens=260,
            temperature=1.2,
        )
        parts = _parse(_clean(rsp.choices[0].message.content))
        if len(parts)>=2 and _valid_first(parts[0]):
            break
    else:
        raise RuntimeError("生成に失敗")
    parts[0] = _insert_break(parts[0])
    parts = [p[:279]+("…" if len(p)>279 else "") for p in parts]
    return parts[:3]

# ───── 重複チェック ─────

def _hash_today(txt):
    return hashlib.md5((datetime.date.today().isoformat()+txt).encode()).hexdigest()

def dup(txt):
    f = LOG_DIR/f"{datetime.date.today():%Y%m%d}.log"
    if f.exists() and _hash_today(txt) in f.read_text().split():
        return True
    f.write_text((f.read_text() if f.exists() else "")+_hash_today(txt)+"\n")
    return False

# ───── 投稿 ─────

def post(parts):
    parts=[_clean(p) for p in parts if p.strip()]
    # 先頭が短ければ単発ツイートへ結合
    if len(parts[0])<110 and len(parts)>=2:
        single = parts[0]+"\n\n"+parts[1]
        if len(parts)>=3:
            single += "\n\n"+parts[2]
        single = single[:279]+("…" if len(single)>279 else "")
        client.create_tweet(text=single)
        print("Tweeted(single):", single[:60])
        return

    head_id = client.create_tweet(text=parts[0]).data["id"]
    print("Tweeted:", parts[0][:60])
    prev_id=head_id
    for body in parts[1:]:
        time.sleep(2)
        prev_id = client.create_tweet(text=body, in_reply_to_tweet_id=prev_id).data["id"]
        print(" replied:", body[:40])

# ───── main ─────

def main():
    parts=generate_thread()
    if dup(parts[0]):
        print("duplicate skip")
        return
    post(parts)

if __name__=="__main__":
    main()
