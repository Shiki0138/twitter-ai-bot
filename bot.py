 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/bot.py b/bot.py
index 92ebdb2..7317c66 100644
--- a/bot.py
+++ b/bot.py
@@ -1,25 +1,26 @@
+# -*- coding: utf-8 -*-
 ###############################################
 # bot.py — Sheets→GPT→X 自動投稿 1日3回版
 # 完全動作版（2025‑05‑18）
 ###############################################
 
 import os, re, json, datetime, textwrap, random
 from typing import List, Dict, Any
 
 import tweepy, openai, gspread
 from google.oauth2.service_account import Credentials
 from dotenv import load_dotenv
 
 # ────────────────── 環境変数 ──────────────────
 load_dotenv()
 openai.api_key = os.getenv("OPENAI_API_KEY")
 API_KEY        = os.getenv("API_KEY")
 API_SECRET     = os.getenv("API_SECRET")
 ACCESS_TOKEN   = os.getenv("ACCESS_TOKEN")
 ACCESS_SECRET  = os.getenv("ACCESS_SECRET")
 SHEET_URL      = os.getenv("SHEET_URL")
 SERVICE_JSON   = os.getenv("GOOGLE_SERVICE_JSON")
 
 # ────────────────── 外部クライアント ──────────
 client = tweepy.Client(
     consumer_key=API_KEY,
diff --git a/bot.py b/bot.py
index 92ebdb2..7317c66 100644
--- a/bot.py
+++ b/bot.py
@@ -33,103 +34,78 @@ SCOPES = [
     "https://www.googleapis.com/auth/spreadsheets",
     "https://www.googleapis.com/auth/drive",
 ]
 if SERVICE_JSON and os.path.isfile(SERVICE_JSON):
     creds = Credentials.from_service_account_file(SERVICE_JSON, scopes=SCOPES)
 else:
     creds = Credentials.from_service_account_info(json.loads(SERVICE_JSON), scopes=SCOPES)
 
 gc = gspread.authorize(creds)
 sheet = gc.open_by_url(SHEET_URL).sheet1
 
 # ────────────────── 定数 ───────────────────────
 THEMES = [
     "美容師のインスタ集客",
     "美容師の集客",
     "美容師の経営戦略",
     "美容室経営者向け情報",
     "美容師の生成AI活用",
 ]
 THEME_REGEX = re.compile("|".join(re.escape(t) for t in THEMES))
 MODEL    = "gpt-4o-mini"
 MAX_LEN  = 140
 EMOJIS   = ["🎯", "💡", "✨", "📈", "🚀"]
 
 # ────────────────── PROMPT TEMPLATE ───────────
-PROMPT_TEMPLATE = rf"""
-あなたはローカルビジネス（美容室・整骨院・個人店など）のマーケティングを専門とするリサーチャー兼コピーライターです。
-
-## Audience
-現場で集客・リピート対策を任されている経営者・店長
-
-## Goal
-100〜140文字の日本語ツイートを {N} 本生成する。
-読んだ相手が『試してみよう』と思う一次情報（数値・調査結果）や顧客心理の“事実”を共有すること。
-
-## Content Rules
-1. **ファクト必須**  
-   ・2022年以降の信頼できる公式データのみ  
-   ・数値を最低1つ含める  
-2. **文字数** 全角換算100〜140。範囲外なら自動で調整  
-3. **書式** 一人称『私』視点の気づきメモ。絵文字・ハッシュタグ・セールス語禁止。  
-   ファクト末尾に簡潔出典 (◯◯調査2024) を括弧書き  
-4. **ジャンル比率** マーケ戦術40％ / 顧客心理40％ / デジタル効率化20％  
-5. **重複禁止** テーマ・数字・出典が被らない  
-6. **品質チェック** 条件外は自動再生成  
 
-## Output Format
-JSON 配列で以下の形式
-[
-  {{"tweet": "ここに100〜140文字の投稿文", "source": "出典URLまたはDOI"}}
-]
-"""
+PROMPT_TEMPLATE = """
 あなたはローカルビジネス（美容室・整骨院・個人店など）のマーケティングを専門とするリサーチャー兼コピーライターです。
 
 ## Audience
 現場で集客・リピート対策を任されている経営者・店長
 
 ## Goal
-100〜140文字の日本語ツイートを {{N}} 本生成する。読んだ相手が『試してみよう』と思う一次情報（数値・調査結果）や顧客心理の“事実”を共有すること。
+100〜140文字の日本語ツイートを {N} 本生成する。読んだ相手が『試してみよう』と思う一次情報（数値・調査結果）や顧客心理の“事実”を共有すること。
 
 ## Content Rules
-1. **ファクト必須**  
-   ・2022年以降の信頼できる公式データのみ  
-   ・数値を最低1つ含める  
-2. **文字数** 全角換算100〜140。範囲外なら自動で調整  
-3. **書式** 一人称『私』視点の気づきメモ。絵文字・ハッシュタグ・セールス語禁止。  
-   ファクト末尾に簡潔出典 (◯◯調査2024) を括弧書き  
-4. **ジャンル比率** マーケ戦術40％ / 顧客心理40％ / デジタル効率化20％  
-5. **重複禁止** テーマ・数字・出典が被らない  
-6. **品質チェック** 条件外は自動再生成  
+1. **ファクト必須**
+   ・2022年以降の信頼できる公式データのみ
+   ・数値を最低1つ含める
+2. **文字数** 全角換算100〜140。範囲外なら自動で調整
+3. **書式** 一人称『私』視点の気づきメモ。絵文字・ハッシュタグ・セールス語禁止。
+
+   ファクト末尾に簡潔出典 (◯◯調査2024) を括弧書き
+4. **ジャンル比率** マーケ戦術40％ / 顧客心理40％ / デジタル効率化20％
+5. **重複禁止** テーマ・数字・出典が被らない
+6. **品質チェック** 条件外は自動再生成
 
 ## Output Format
 JSON 配列で以下の形式
 [
   {{"tweet": "ここに100〜140文字の投稿文", "source": "出典URLまたはDOI"}}
 ]
 """
-
 RE_JSON_ARRAY = re.compile(r"\[.*?\]", re.S)
 
 # ────────────────── GPT Wrapper ──────────────
 
 def generate_tweet(raw: str) -> List[str]:
     prompt = PROMPT_TEMPLATE.format(N=1)
     payload = f"原文:\n{raw}"
     res = openai.chat.completions.create(
         model=MODEL,
         messages=[
             {"role": "user", "content": prompt},
             {"role": "user", "content": payload},
         ],
         temperature=0.8,
     ).choices[0].message.content
 
     match = RE_JSON_ARRAY.search(res)
     if not match:
         raise ValueError("GPT output is not JSON array")
     data = json.loads(match.group(0))
     tweet = data[0]["tweet"]
     if len(tweet) > MAX_LEN:
         tweet = tweet[:MAX_LEN]
     return [tweet]
 
 
EOF
)
