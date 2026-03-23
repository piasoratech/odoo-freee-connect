#!/usr/bin/env python3
"""
freee 初回OAuth認証スクリプト
.freee_token.json を生成する（初回のみ実行）
"""
import json
import os
import webbrowser
from pathlib import Path
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ["FREEE_CLIENT_ID"]
CLIENT_SECRET = os.environ["FREEE_CLIENT_SECRET"]
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
TOKEN_FILE = Path(".freee_token.json")

AUTH_URL = "https://accounts.secure.freee.co.jp/public_api/authorize"
TOKEN_URL = "https://accounts.secure.freee.co.jp/public_api/token"


def main():
    # 1. 認証URLを生成してブラウザで開く
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
    }
    auth_url = f"{AUTH_URL}?{urlencode(params)}"

    print("=== freee 初回OAuth認証 ===")
    print("\n以下のURLをブラウザで開いてfreeeにログインし、認証コードを取得してください：")
    print(f"\n{auth_url}\n")
    webbrowser.open(auth_url)

    # 2. 認証コードを入力
    code = input("認証コードを貼り付けてください: ").strip()

    # 3. アクセストークンを取得
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }, timeout=30)
    resp.raise_for_status()
    token_data = resp.json()

    # 4. トークンを保存
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

    print(f"\n✅ トークンを {TOKEN_FILE} に保存しました")
    print(f"   access_token: {token_data['access_token'][:20]}...")
    print(f"   expires_in:   {token_data.get('expires_in')}秒")


if __name__ == "__main__":
    main()
