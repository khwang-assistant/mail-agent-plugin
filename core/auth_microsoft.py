import os
import sys
import json
import requests
import msal
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID", "").strip()
AUTHORITY = "https://login.microsoftonline.com/consumers"
SCOPES = ["Mail.ReadWrite", "Mail.Read", "User.Read"]
TOKEN_CACHE_FILE = "token_hotmail.json"
FALLBACK_TOKEN_CACHE_FILE = "token_microsoft.json"

def get_token_cache():
    cache = msal.SerializableTokenCache()
    target_file = TOKEN_CACHE_FILE if os.path.exists(TOKEN_CACHE_FILE) else FALLBACK_TOKEN_CACHE_FILE
    if os.path.exists(target_file):
        try:
            with open(target_file, "r", encoding="utf-8") as f:
                cache.deserialize(f.read())
        except Exception as e:
            print(f"[WARN] 讀取 token 快取失敗: {e}")
    return cache

def save_token_cache(cache):
    if cache.has_state_changed:
        target_file = TOKEN_CACHE_FILE if os.path.exists(TOKEN_CACHE_FILE) else (FALLBACK_TOKEN_CACHE_FILE if os.path.exists(FALLBACK_TOKEN_CACHE_FILE) else TOKEN_CACHE_FILE)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(cache.serialize())

def get_microsoft_access_token():
    """取得 Microsoft Graph API Access Token (自動從快取取得或靜默更新，若無則啟動瀏覽器互動授權)"""
    if not CLIENT_ID:
        raise ValueError("[ERROR] 未在環境變數中找到 MICROSOFT_CLIENT_ID，請先設定！")

    cache = get_token_cache()
    app = msal.PublicClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache
    )

    accounts = app.get_accounts()
    result = None

    if accounts:
        # 嘗試從快取中靜默取得 Token (若過期會自動使用 refresh token 換發)
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not result:
        print("[INFO] 正在啟動微軟 OAuth 瀏覽器登入授權...")
        print("[INFO] 系統將開啟瀏覽器，請在登入後確認授權。")
        try:
            result = app.acquire_token_interactive(scopes=SCOPES)
        except Exception as e:
            print(f"[ERROR] 互動式登入失敗: {e}")
            raise

    if "access_token" in result:
        save_token_cache(cache)
        return result["access_token"]
    else:
        error_desc = result.get("error_description", result.get("error"))
        raise RuntimeError(f"[ERROR] 微軟授權失敗: {error_desc}")

def get_hotmial_headers():
    token = get_microsoft_access_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

if __name__ == "__main__":
    print("==================================================")
    print("微軟 Hotmail/Outlook OAuth 2.0 授權測試")
    print("==================================================")
    
    try:
        token = get_microsoft_access_token()
        print("\n[SUCCESS] 微軟帳號授權成功，已生成 token_hotmail.json 快取憑證。")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # 測試呼叫 Graph API 取得個人資訊
        me_resp = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers)
        if me_resp.status_code == 200:
            user_data = me_resp.json()
            display_name = user_data.get("displayName", "")
            mail = user_data.get("mail") or user_data.get("userPrincipalName", "")
            masked_mail = mail[:2] + "***@" + mail.split("@")[-1] if "@" in mail else mail
            print(f"帳戶名稱：{display_name} ({masked_mail})")
            
        # 測試呼叫收件匣取得未讀郵件數量
        inbox_resp = requests.get("https://graph.microsoft.com/v1.0/me/mailFolders/inbox", headers=headers)
        if inbox_resp.status_code == 200:
            inbox_data = inbox_resp.json()
            unread_count = inbox_data.get("unreadItemCount", 0)
            total_count = inbox_data.get("totalItemCount", 0)
            print(f"收件匣總信件：{total_count} 封 | 未讀信件：{unread_count} 封")
        else:
            print(f"[WARN] 讀取收件匣狀態碼: {inbox_resp.status_code}")
            
        print("==================================================")
    except Exception as e:
        print(f"\n[ERROR] 發生錯誤: {e}")
        sys.exit(1)
