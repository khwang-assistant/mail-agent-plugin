import os
import sys
import abc
import requests
from typing import List, Dict, Any, Optional

try:
    from core.auth_gmail import get_gmail_service
except ImportError:
    try:
        from auth_gmail import get_gmail_service
    except ImportError:
        get_gmail_service = None

try:
    from core.auth_microsoft import get_microsoft_access_token
except ImportError:
    try:
        from auth_microsoft import get_microsoft_access_token
    except ImportError:
        get_microsoft_access_token = None


class BaseEmailProvider(abc.ABC):
    """信箱服務提供者抽象介面"""

    @abc.abstractmethod
    def fetch_unread_emails(self, limit: int = 100) -> List[Dict[str, Any]]:
        """讀取收件匣未讀信件清單，回傳標準化字典列表：
        [
            {
                "id": str,
                "subject": str,
                "sender": str,
                "date": str,
                "snippet": str,
                "has_pdf": bool
            }
        ]
        """
        pass

    @abc.abstractmethod
    def get_or_create_destination(self, name: str) -> str:
        """取得或建立目標標籤/資料夾，回傳唯一標籤或資料夾 ID"""
        pass

    @abc.abstractmethod
    def move_email(self, email_id: str, dest_id: str) -> None:
        """將信件移入目標分類並移出收件匣（必須維持未讀狀態）"""
        pass

    @abc.abstractmethod
    def restore_email(self, email_id: str, original_dest_id: str) -> None:
        """將信件還原回收件匣並解除目標分類"""
        pass


class HotmailProvider(BaseEmailProvider):
    """Microsoft Hotmail / Outlook.com 提供者 (基於 Microsoft Graph API)"""

    def __init__(self, token: Optional[str] = None):
        self._token = token
        self._folder_cache: Dict[str, str] = {}

    def _get_headers(self) -> Dict[str, str]:
        token = self._token or (get_microsoft_access_token() if get_microsoft_access_token else None)
        if not token:
            raise RuntimeError("[ERROR] 無法取得微軟 Access Token，請先設定 MICROSOFT_CLIENT_ID 並完成授權！")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def fetch_unread_emails(self, limit: int = 100) -> List[Dict[str, Any]]:
        headers = self._get_headers()
        url = (
            f"https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages"
            f"?$filter=isRead eq false&$top={limit}"
            f"&$select=id,subject,from,receivedDateTime,bodyPreview,hasAttachments"
        )
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"[ERROR] 讀取 Hotmail 收件匣失敗 ({resp.status_code}): {resp.text}")

        messages = resp.json().get("value", [])
        normalized = []
        for msg in messages:
            from_info = msg.get("from", {}).get("emailAddress", {})
            name = from_info.get("name", "")
            address = from_info.get("address", "")
            sender_str = f"{name} <{address}>" if name else address

            normalized.append({
                "id": msg.get("id"),
                "subject": msg.get("subject", ""),
                "sender": sender_str,
                "date": msg.get("receivedDateTime", ""),
                "snippet": msg.get("bodyPreview", ""),
                "has_pdf": msg.get("hasAttachments", False)
            })
        return normalized

    def get_or_create_destination(self, name: str) -> str:
        # Outlook 資料夾名稱將斜線轉換為破折號避免路徑解析異常
        folder_display_name = name.replace("/", " - ").strip()
        if folder_display_name in self._folder_cache:
            return self._folder_cache[folder_display_name]

        headers = self._get_headers()
        # 查詢現有資料夾
        list_url = f"https://graph.microsoft.com/v1.0/me/mailFolders?$top=100"
        resp = requests.get(list_url, headers=headers)
        if resp.status_code == 200:
            for folder in resp.json().get("value", []):
                if folder.get("displayName") == folder_display_name:
                    fid = folder.get("id")
                    self._folder_cache[folder_display_name] = fid
                    return fid

        # 若不存在則建立新資料夾
        create_url = "https://graph.microsoft.com/v1.0/me/mailFolders"
        create_resp = requests.post(create_url, headers=headers, json={"displayName": folder_display_name})
        if create_resp.status_code in (200, 201):
            fid = create_resp.json().get("id")
            self._folder_cache[folder_display_name] = fid
            return fid
        else:
            raise RuntimeError(f"[ERROR] 建立 Hotmail 資料夾 '{folder_display_name}' 失敗: {create_resp.text}")

    def move_email(self, email_id: str, dest_id: str) -> None:
        headers = self._get_headers()
        move_url = f"https://graph.microsoft.com/v1.0/me/messages/{email_id}/move"
        resp = requests.post(move_url, headers=headers, json={"destinationId": dest_id})
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"[ERROR] 搬移信件 {email_id} 失敗 ({resp.status_code}): {resp.text}")

    def restore_email(self, email_id: str, original_dest_id: str) -> None:
        headers = self._get_headers()
        move_url = f"https://graph.microsoft.com/v1.0/me/messages/{email_id}/move"
        # 微軟 Graph API 原生支援搬移回 "inbox"
        resp = requests.post(move_url, headers=headers, json={"destinationId": "inbox"})
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"[ERROR] 還原信件 {email_id} 回收件匣失敗 ({resp.status_code}): {resp.text}")


class GmailProvider(BaseEmailProvider):
    """Google Gmail 提供者 (基於 Gmail REST API)"""

    def __init__(self, service: Any = None):
        self._service = service or (get_gmail_service() if get_gmail_service else None)
        self._label_cache: Dict[str, str] = {}

    def _ensure_service(self):
        if not self._service:
            if get_gmail_service:
                self._service = get_gmail_service()
            else:
                raise RuntimeError("[ERROR] 無法初始化 Gmail 服務，請確認已完成 token_gmail.json 授權！")

    def fetch_unread_emails(self, limit: int = 100) -> List[Dict[str, Any]]:
        self._ensure_service()
        results = self._service.users().messages().list(
            userId='me', q='label:INBOX is:unread', maxResults=limit
        ).execute()
        messages = results.get('messages', [])
        
        normalized = []
        for m in messages:
            msg_id = m['id']
            msg = self._service.users().messages().get(
                userId='me', id=msg_id, format='metadata',
                metadataHeaders=['Subject', 'From', 'Date']
            ).execute()
            headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}
            normalized.append({
                "id": msg_id,
                "subject": headers.get('Subject', '(無主旨)'),
                "sender": headers.get('From', '(未知寄件者)'),
                "date": headers.get('Date', ''),
                "snippet": msg.get('snippet', ''),
                "has_pdf": False
            })
        return normalized

    def get_or_create_destination(self, name: str) -> str:
        self._ensure_service()
        if name in self._label_cache:
            return self._label_cache[name]

        labels = self._service.users().labels().list(userId='me').execute().get('labels', [])
        for label in labels:
            if label['name'] == name:
                self._label_cache[name] = label['id']
                return label['id']

        created = self._service.users().labels().create(
            userId='me',
            body={
                'name': name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }
        ).execute()
        self._label_cache[name] = created['id']
        return created['id']

    def move_email(self, email_id: str, dest_id: str) -> None:
        self._ensure_service()
        self._service.users().messages().batchModify(
            userId='me',
            body={
                'ids': [email_id],
                'addLabelIds': [dest_id],
                'removeLabelIds': ['INBOX']
            }
        ).execute()

    def restore_email(self, email_id: str, original_dest_id: str) -> None:
        self._ensure_service()
        self._service.users().messages().batchModify(
            userId='me',
            body={
                'ids': [email_id],
                'addLabelIds': ['INBOX'],
                'removeLabelIds': [original_dest_id]
            }
        ).execute()
