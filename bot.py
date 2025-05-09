# bot.py — ラベル除去版：Tweet1/Tweet2 表記を投稿前に完全削除
# =====================================================================
# (その他の仕様はそのまま)
#   • ChatGPT からは Tweet1:/Tweet2: ラベル付きで受け取り
#   • 投稿前に正規表現で "Tweet\d+:" を除去 → すっきり表示
# ---------------------------------------------------------------------

import os, re, random, time, hashlib, datetime, unicodedata
from pathlib import Path

import openai, tweepy
from dotenv import load_dotenv

# ── 環境変数 ─────────────────────────────────────────
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
API_KEY        = os.getenv("API_KEY")
API_SECRET     = os.getenv("API_SECRET")
ACCESS_TOKEN   = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET  = os.getenv("ACCESS_SECRET")

client = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET,
)

# ── ログ ────────────────────────────────────────────
LOG_DIR = Path("tweet_logs"); LOG_DIR.mkdir(exist_ok=True)

def _hash_today(txt:str)->str:
    today = datetime.date.today().isoformat()
    return hashlib.md5((today+txt).encode()).hexdigest()

def is_duplicate(txt:str)->bool:
    h = _hash_today(txt)
    f = LOG_DIR/f"{datetime.date.today():%Y%m%d}.log"
    if f.exists() and h in f.read_text().split():
        return True
    f.write_text((f.read_text() if f.exists() else "")+h+"\n")
    return False

# ── データ ───────────────────────────────────────────
TEMPLATES=["質問フック型","驚き事例型","課題解決ステップ型","ストーリー共感型"]
STAT_POOL=["米国中小企業の83%がAIで業務効率化を実感（BPC調査）",...]
FACT_POOL=["ロンドン美容室BleachはAI活用SNSで新規予約20%増",...]

MODEL="gpt-4o-mini"; TEMP=1.2; TOP_P=1; MAX_TOKENS=350
MIN_LEN,MAX_LEN,THRESH=100,140,110
RE_SURPRISE=re.compile(r"[!！]|驚|衝撃")

# ── util ───────────────────────────────────────────
import unicodedata

def _clean(t:str)->str:
    t=unicodedata.normalize("NFC",t);return t.encode("utf-8","ignore").decode()

def _insert_break(t:str,limit:int=120)->str:
    t=t.strip();
    if len(t)<=limit:return t
    for m in "。.!?！？":
        p=t.rfind(m,50,limit)
        if p!=-1:return t[:p+1]+"\n"+t[p+1:]
    return t[:limit]+"\n"+t[limit:]

def _parse(raw:str)->list[str]:
    pts=re.findall(r"Tweet\d+:\s*(.+)",raw,flags=re.I)
    return pts or [p.strip() for p in raw.split("\n") if p.strip()]

def valid_first(t:str)->bool:
    return MIN_LEN<=len(t)<=MAX_LEN and RE_SURPRISE.search(t) and re.search(r"\d",t)

# ── 生成 ───────────────────────────────────────────
PROMPT_TMPL=("あなたはSNSマーケター兼リサーチャーです。"...
)

def generate_thread()->list[str]:
    template=random.choice(TEMPLATES);
    stat=random.choice(STAT_POOL);fact=random.choice(FACT_POOL)
    prompt=PROMPT_TMPL.format(stat=stat,fact=fact,template=template)
    for _ in range(5):
        raw=_clean(openai.chat.completions.create(
            model=MODEL,messages=[{"role":"user","content":prompt}],
            max_tokens=MAX_TOKENS,temperature=TEMP,top_p=TOP_P).choices[0].message.content)
        parts=_parse(raw)
        if len(parts)<2:continue
        parts[0]=_insert_break(parts[0]);
        if valid_first(parts[0]):break
    else:
        raw=_clean(openai.chat.completions.create(model=MODEL,messages=[{"role":"user","content":prompt.replace("100–140","90–140")}],max_tokens=MAX_TOKENS,temperature=TEMP,top_p=TOP_P).choices[0].message.content)
        parts=_parse(raw)
    if not parts:raise RuntimeError("生成失敗")
    if len(parts)==1:
        txt=parts[0];cut=max(60,len(txt)//2);parts=[txt[:cut],txt[cut:]]
    trimmed=[]
    for p in parts[:3]:
        p=re.sub(r"^Tweet\d+:\s*","",p)     # ★ ラベル削除 ★
        p=p.strip()
        if len(p)>MAX_LEN:p=p[:MAX_LEN-1]+"…"
        trimmed.append(_clean(p))
    return [t for t in trimmed if t]

# ── 投稿 ────────────────────────────────────────────

def post(parts:list[str]):
    if len(parts)>=2 and len(parts[0])<THRESH:
        single=parts[0]+"\n\n"+"\n\n".join(parts[1:])
        single=single[:279]+("…" if len(single)>279 else "")
        client.create_tweet(text=single);print("Tweeted(single):",single[:60],"…");return
    head=client.create_tweet(text=parts[0]).data["id"];print("Tweeted:",parts[0])
    prev=head
    for b in parts[1:]:
        time.sleep(2);prev=client.create_tweet(text=b,in_reply_to_tweet_id=prev).data["id"]
        print(" replied:",b[:40],"…")

# ── main ───────────────────────────────────────────

def main():
    parts=generate_thread()
    if is_duplicate(parts[0]):print("Duplicate. skip");return
    try:post(parts)
    except Exception as e:
        print("⚠️",e);client.create_tweet(text=parts[0][:MAX_LEN])

if __name__=="__main__":
    main()
