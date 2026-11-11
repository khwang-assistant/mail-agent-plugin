import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# gmail.modify lets us read emails, mark read, and manage labels without delete or send access
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

TOKEN_FILE = 'token_gmail.json'
FALLBACK_TOKEN_FILE = 'token.json'

def get_gmail_service():
    creds = None
    target_token_file = TOKEN_FILE if os.path.exists(TOKEN_FILE) else FALLBACK_TOKEN_FILE

    if os.path.exists(target_token_file):
        creds = Credentials.from_authorized_user_file(target_token_file, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES
            )
            # This opens your default browser for you to click "Allow"
            creds = flow.run_local_server(port=0)
        
        # Save credentials for future runs
        save_file = target_token_file if os.path.exists(target_token_file) else TOKEN_FILE
        with open(save_file, 'w') as token:
            token.write(creds.to_json())
            print(f"[SUCCESS] 授權成功，已產生 {save_file} 快取憑證。")
    
    service = build('gmail', 'v1', credentials=creds)
    return service

if __name__ == '__main__':
    print("[INFO] 正在啟動 Google OAuth 登入驗證...")
    service = get_gmail_service()
    print("[SUCCESS] 成功連線至 Gmail 信箱。")
