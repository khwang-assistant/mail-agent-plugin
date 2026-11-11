import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Ensure plugin root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.providers import BaseEmailProvider, HotmailProvider, GmailProvider

class TestProviders(unittest.TestCase):
    def test_base_provider_cannot_instantiate(self):
        with self.assertRaises(TypeError):
            BaseEmailProvider()

    @patch("core.providers.requests.get")
    def test_hotmail_fetch_unread_emails(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "value": [
                {
                    "id": "msg_123",
                    "subject": "Test Promo Subject",
                    "from": {"emailAddress": {"name": "Amazon Deals", "address": "deals@amazon.com"}},
                    "receivedDateTime": "2026-11-11T12:00:00Z",
                    "bodyPreview": "Save big this week on electronics!",
                    "hasAttachments": False
                }
            ]
        }
        mock_get.return_value = mock_resp

        provider = HotmailProvider(token="mock_token")
        emails = provider.fetch_unread_emails(limit=10)
        
        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0]["id"], "msg_123")
        self.assertEqual(emails[0]["subject"], "Test Promo Subject")
        self.assertEqual(emails[0]["sender"], "Amazon Deals <deals@amazon.com>")
        self.assertIn("Save big", emails[0]["snippet"])

    @patch("core.providers.requests.post")
    def test_hotmail_move_email(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_post.return_value = mock_resp

        provider = HotmailProvider(token="mock_token")
        provider.move_email("msg_123", "dest_folder_456")
        
        mock_post.assert_called_once_with(
            "https://graph.microsoft.com/v1.0/me/messages/msg_123/move",
            headers={"Authorization": "Bearer mock_token", "Content-Type": "application/json"},
            json={"destinationId": "dest_folder_456"}
        )

if __name__ == "__main__":
    unittest.main()
