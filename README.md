# Mail Agent Plugin for Antigravity

[![Antigravity Plugin](https://img.shields.io/badge/Antigravity-Plugin-blue.svg)](https://github.com/khwang-assistant/mail-agent-plugin)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

跨平台郵件智慧分類與自動化處理外掛，原生支援 Google Gmail 與 Microsoft Hotmail / Outlook.com。

---

## 包含的 Skills (Included Skills)

| Skill 名稱 | 說明 | 支援信箱 | 狀態 |
| :--- | :--- | :---: | :---: |
| **`promotion-cleaner`** | 辨識行銷促銷郵件、支援分類標籤與資料夾分流、保留原始未讀狀態、交易紀錄還原機制與雲端排程。 | Gmail / Hotmail | 正式支援 |
| **`bank-statement-tracker`** | 辨識銀行綜合對帳單、本地安全解密 PDF、提取結餘數據並對齊試算表。 | 全信箱通用 | 開發中 |

---

## 安裝方式 (Installation)

### 方法一：透過 Antigravity 安裝 Plugin
在專案或 Antigravity 環境中執行：
```bash
agy plugin install khwang-assistant/mail-agent-plugin
```

### 方法二：作為 Git Submodule 引入至個人 Runner
若欲建立專屬的 GitHub Actions 定時執行儲存庫：
```bash
git submodule add https://github.com/khwang-assistant/mail-agent-plugin.git plugin
```

---

## 前置需求 (Prerequisites)

1. Python 3.10+
2. Google Gemini API Key（具備 15 RPM 額度）
3. 信箱服務授權憑證（依使用信箱配置）：
   - **Gmail**：
     - 於 Google Cloud Console 啟用 Gmail API。
     - 建立憑證類型：桌面應用程式 (Desktop App)。
     - 授權範圍 (Scope)：`https://www.googleapis.com/auth/gmail.modify`。
     - 下載憑證檔案並命名為 `credentials.json` 放置於根目錄。
   - **Hotmail / Outlook.com**：
     - 於 Azure 應用程式註冊建立應用程式。
     - 帳戶類型：任何組織目錄中的帳戶與個人 Microsoft 帳戶。
     - 重新導向 URI：行動和傳統型應用程式，設定 `http://localhost`。
     - API 權限：Microsoft Graph 委派權限 `Mail.ReadWrite`、`Mail.Read`、`User.Read`。
     - 複製 Application (client) ID。

---

## 快速上手 (Quick Start)

### 1. 安裝相依套件
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置環境變數
建立 `.env` 檔案：
```bash
GEMINI_API_KEY=your_gemini_api_key_here

# 使用 Hotmail / Outlook 時需設定:
MICROSOFT_CLIENT_ID=your_microsoft_client_id_here
```

### 3. 初次登入授權
* **Gmail 使用者**：
  ```bash
  python core/auth_gmail.py
  ```
  > 瀏覽器開啟授權視窗，確認後於本機生成憑證 `token_gmail.json`。

* **Hotmail / Outlook 使用者**：
  ```bash
  python core/auth_microsoft.py
  ```
  > 瀏覽器開啟微軟登入視窗，授權完成後於本機生成憑證 `token_hotmail.json`。

### 4. 配置分類規則 (Provider 規則隔離)

系統支援依照信箱自動讀取專屬規則檔：

#### 配置 Gmail 規則（複製 `rules.gmail.example.yaml`）
```bash
cp skills/promotion-cleaner/rules.gmail.example.yaml rules.gmail.yaml
```
```yaml
provider: "gmail"

labels:
  parent: "MailAgent/廣告信"
  other: "MailAgent/廣告信/其他"

custom_rules:
  - id: "AMAZON"
    label_name: "Amazon"
    domain_guardrail: "amazon"
    description: "Amazon 線上購物促銷與特惠信件"

  - id: "LINKEDIN"
    label_name: "LinkedIn"
    domain_guardrail: "linkedin.com"
    description: "LinkedIn 人脈動態與職場精選推薦"

  - id: "UBEREATS"
    label_name: "UberEats"
    domain_guardrail: "ubereats"
    description: "UberEats 美食外送優惠券與折扣信件"

safe_rules:
  - "個人通訊、工作往來信件。"
  - "銀行綜合對帳單、信用卡帳單、水電繳費通知、電子發票。"
  - "密碼重設、帳戶安全性快訊、雙步驟驗證碼 (2FA)。"
```

#### 配置 Hotmail 規則（複製 `rules.hotmail.example.yaml`）
```bash
cp skills/promotion-cleaner/rules.hotmail.example.yaml rules.hotmail.yaml
```
```yaml
provider: "hotmail"

labels:
  parent: "MailAgent - 廣告信"
  other: "MailAgent - 廣告信 - 其他"

custom_rules:
  - id: "AMAZON"
    label_name: "Amazon"
    domain_guardrail: "amazon"
    description: "Amazon 線上購物促銷與特惠信件"

  - id: "SUBSTACK"
    label_name: "Substack"
    domain_guardrail: "substack.com"
    description: "Substack 知識專欄與電子報"

safe_rules:
  - "微軟帳戶安全性警示、單次登入驗證碼、備援信箱通知。"
  - "Microsoft 官方電子發票、各銀行對帳單、信用卡帳單。"
  - "個人通訊、工作往來信件。"
```

---

## 命令列操作說明 (CLI Usage)

執行時須透過 `--provider` 明確指定信箱對象（或由規則設定檔指定），防止跨信箱誤操作。

### 1. 預覽整理結果 (Dry Run - 僅分析不更動)
```bash
# 預覽 Gmail (自動讀取 rules.gmail.yaml)
python skills/promotion-cleaner/clean_promotions.py --provider gmail --limit 20

# 預覽 Hotmail / Outlook (自動讀取 rules.hotmail.yaml)
python skills/promotion-cleaner/clean_promotions.py --provider hotmail --limit 20
```

### 2. 正式執行整理 (Live Run)
```bash
# 正式整理 Gmail
python skills/promotion-cleaner/clean_promotions.py --provider gmail --live --limit 50

# 正式整理 Hotmail / Outlook
python skills/promotion-cleaner/clean_promotions.py --provider hotmail --live --limit 50
```
> **未讀狀態保留機制**：郵件歸檔至指定標籤或資料夾並移出收件匣時，系統完整維持其未讀狀態（保持 isRead: false / UNREAD 旗標），不影響視覺標示。

### 3. 還原作業 (Rollback)
```bash
# 檢視歷史清理紀錄 (自動辨識 GMAIL 或 HOTMAIL)
python skills/promotion-cleaner/rollback.py --list

# 還原最近一次整理 (將郵件回復至收件匣並解除標籤/資料夾)
python skills/promotion-cleaner/rollback.py --last
```

---

## 專案目錄結構 (Project Structure)

```text
mail-agent-plugin/
├── AGENTS.md                       # 外掛架構與工程開發規範
├── plugin.json                     # 外掛定義檔
├── README.md                       # 外掛使用手冊
├── requirements.txt                # 依賴套件清單
├── LICENSE                         # MIT 開源授權
│
├── core/                           # 跨服務共用模組
│   ├── __init__.py
│   ├── auth_gmail.py               # Gmail API 授權與 Token 處理
│   ├── auth_microsoft.py           # Microsoft OAuth 處理
│   └── providers.py                # 信箱服務抽象化介面 (Gmail & Hotmail)
│
├── skills/                         # 技能模組庫
│   ├── promotion-cleaner/          # 促銷郵件分類技能 (支援 Gmail & Hotmail)
│   │   ├── SKILL.md                # 技能定義文件
│   │   ├── clean_promotions.py     # 分類執行腳本 (強制 --provider 檢查)
│   │   ├── rollback.py             # 還原工具 (自動辨識信箱服務)
│   │   ├── rules.gmail.example.yaml   # Gmail 規則範本
│   │   └── rules.hotmail.example.yaml # Hotmail 規則範本
│   │
│   └── bank-statement-tracker/      # 銀行對帳單解析技能 (開發中)
│       └── SKILL.md
│
└── tests/
    └── test_providers.py           # 單元測試
```

---

## 資訊安全與隱私規範 (Security & Privacy)

* **零機敏資料外洩原則**：密碼、未遮罩之身分證字號與銀行帳號嚴禁傳送至大型語言模型 API。
* **本地記憶體解密**：對帳單 PDF 僅於本地記憶體解密處理，密碼不落地。
* **版本控制隔離**：`.env`、`token*.json`（`token_gmail.json`, `token_hotmail.json`）、`credentials.json`、`rules*.yaml` 預設列入 `.gitignore`。

---

## 授權條款 (License)

本專案採用 [MIT License](LICENSE) 開源授權。
