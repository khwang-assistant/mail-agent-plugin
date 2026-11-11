import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# gmail.modify lets us read emails, mark read, and manage labels without delete or send access
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def get_gmail_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
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
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            print(">>> 授權成功！已產生 token.json 憑證。")
    
    service = build('gmail', 'v1', credentials=creds)
    return service

if __name__ == '__main__':
    print(">>> 正在啟動 Google OAuth 登入驗證...")
    service = get_gmail_service()
    print(">>> 成功連線到 Gmail 信箱！")
