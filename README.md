# 📬 Mail Agent Plugin for Antigravity

[![Antigravity Plugin](https://img.shields.io/badge/Antigravity-Plugin-blue.svg)](https://github.com/khwang-assistant/mail-agent-plugin)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

一個為 AI Coding Assistant（Google Antigravity、Claude Code、Cursor 等）設計的智慧 Gmail 信箱整理與自動化插件。

---

## 🌟 包含的 Skills (Included Skills)

| Skill 名稱 | 說明 | 狀態 |
| :--- | :--- | :---: |
| **`gmail-promotion-cleaner`** | 智慧辨識行銷廣告 EDM、支援客製化品牌子標籤、B-mode 維持未讀、一鍵復原與 GitHub Actions 雲端巡邏。 | ✅ 正式支援 |
| **`bank-statement-tracker`** | 辨識銀行對帳單、本地安全解密 PDF、提取各期活定存結餘並同步試算表。 | 🚧 開發中 |

---

## 🚀 快速安裝 (Installation)

### 方法一：透過 Antigravity 安裝 Plugin
在您的專案或 Antigravity 環境中執行：
```bash
agy plugin install khwang-assistant/mail-agent-plugin
```

### 方法二：作為 Git Submodule 引入至個人 Runner
如果您想建立專屬的 GitHub Actions 定時執行倉庫：
```bash
git submodule add https://github.com/khwang-assistant/mail-agent-plugin.git plugin
```

---

## 🛠️ 前置需求 (Prerequisites)

1. **Python 3.10+**
2. **Google Gemini API Key**（免費申請，具備 15 RPM 額度）
3. **Google Cloud Console OAuth 2.0 Client Credentials**：
   - 啟用 **Gmail API**。
   - 建立憑證類型：**桌面應用程式 (Desktop App)**。
   - 權限範圍 (Scope)：`https://www.googleapis.com/auth/gmail.modify`。
   - 下載金鑰並命名為 `credentials.json`。

---

## ⚙️ 快速上手 (Quick Start)

### 1. 安裝相依套件
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 設定環境變數
建立 `.env` 檔案：
```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. 初次 Google 授權
將下載的 `credentials.json` 放置於專案根目錄，執行：
```bash
python core/auth_gmail.py
```
> 瀏覽器會開啟授權視窗，登入後即自動在本地生成安全權限檔 `token.json`。

### 4. 建立您的分類規則
複製範本並自訂您的品牌規則：
```bash
cp skills/gmail-promotion-cleaner/rules.example.yaml rules.yaml
```
編輯 `rules.yaml` 加入您想要過濾的品牌與網域防呆：
```yaml
labels:
  parent: "MailAgent/廣告信"
  other: "MailAgent/廣告信/其他"

custom_rules:
  - id: "COSTCO"
    label_name: "Costco"
    domain_guardrail: "costco"
    description: "好市多線上購物與促銷信件"

  - id: "COUPANG"
    label_name: "Coupang"
    domain_guardrail: "coupang"
    description: "酷澎商品推薦與特賣促銷"
```

---

## 💻 常用 CLI 操作

### 1. 預覽整理結果 (Dry Run - 安全無副作用)
```bash
python skills/gmail-promotion-cleaner/clean_promotions.py --limit 20
```

### 2. 正式執行整理 (Live Run)
```bash
python skills/gmail-promotion-cleaner/clean_promotions.py --live --limit 50
```
> 🎯 **B-Mode 機制**：被整理的廣告信件會貼上標籤並移出收件匣，但**保持「未讀」（粗體）狀態**。

### 3. 一鍵復原 / 還原 (Rollback)
```bash
# 檢視歷史清理紀錄
python skills/gmail-promotion-cleaner/rollback.py --list

# 還原最近一次整理 (把信件搬回收件匣並撕掉標籤)
python skills/gmail-promotion-cleaner/rollback.py --last
```

---

## 📂 專案目錄結構 (Project Structure)

```text
mail-agent-plugin/
├── plugin.json                    # 外掛定義檔
├── README.md                      # 外掛使用手冊
├── requirements.txt               # 依賴套件清單
├── LICENSE                        # MIT 開源授權
│
├── core/                          # 跨 Skill 共用核心模組
│   ├── __init__.py
│   └── auth_gmail.py              # Gmail API 授權與 Token 處理
│
└── skills/                        # 外掛技能庫 (自成一體)
    ├── gmail-promotion-cleaner/    # 廣告信自動整理技能
    │   ├── SKILL.md               # Agent 技能指引
    │   ├── clean_promotions.py    # 分類主腳本
    │   ├── rollback.py            # 復原工具
    │   └── rules.example.yaml     # 規則設定範本
    │
    └── bank-statement-tracker/     # 銀行對帳單自動解析 (即將推出)
        └── SKILL.md
```

---

## 🔒 資訊安全與隱私規範 (Security & Privacy)

* **零資料外洩原則**：個人帳單密碼、未遮罩身分證字號與銀行帳號**絕對不傳送至外部 LLM API**。
* **本地記憶體解密**：銀行對帳單 PDF 僅在本地 CPU/RAM 中利用開源函式庫解密，密碼不落地。
* **嚴格 Git 衛生**：`.env`、`token.json`、`credentials.json`、`rules.yaml`（個人規則）預設列入 `.gitignore`。

---

## 📄 授權條款 (License)

本專案採用 [MIT License](LICENSE) 開源授權。
