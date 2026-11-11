# AGENTS.md - Mail Agent Plugin 架構規範與開發守則

本文件定義 `mail-agent-plugin` 核心外掛的系統架構、資安邊界、編程規範與文檔用語準則。所有參與本專案開發之 AI Agent 與開發者均須嚴格遵守。

---

## 1. 系統目標與定位 (System Scope)

`mail-agent-plugin` 為跨信箱平台的智慧郵件分類與自動化外掛，核心目標：
1. **行銷廣告郵件自動分流**：辨識行銷促銷郵件（EDM）、活動推薦與電子報，並依據規則安全移出收件匣（Inbox），分類至專屬標籤或資料夾。
2. **多信箱服務相容**：原生支援 Google Gmail（REST API）與 Microsoft Hotmail/Outlook.com（Microsoft Graph API），具備抽象化擴充架構。
3. **重要通知嚴格保留**：系統安全性快訊、雙步驟驗證碼（2FA）、金融帳單、電子發票與個人公務通訊，絕不進行封存或異動。

---

## 2. 文檔與用語規範 (Documentation & Communication Standards)

為維持專案的專業工程品質與跨團隊易讀性，遵循以下規範：

### 2.1 避免過度使用 Emoji (Minimal Emoji Usage)
* 文檔與程式碼日誌應維持簡潔嚴謹的工程風格。
* 僅在表示核心技術狀態（如必要之警示項目）時少量使用，嚴禁在標題、段落及終端機輸出中濫用裝飾性 Emoji。

### 2.2 採用正式工程術語 (Formal Engineering Terminology)
* 禁止在公開文檔、代碼註解或 Log 中使用口語、內部討論代稱或俚語。
  - **禁用**：「B-mode」、「貼標籤」、「粗體未讀」、「撕標籤」、「井水不犯河水」。
  - **正式術語**：
    - 「保留未讀狀態（Preserve Unread Status）」：處理郵件時完整維持其原始未讀旗標（`isRead: false` / `UNREAD`）。
    - 「歸檔至分類標籤 / 資料夾（Archive to Label / Folder）」：將郵件移入目標分類並自收件匣移除。
    - 「還原作業（Rollback / Revert）」：依據交易日誌將郵件回復至收件匣初始狀態。
* 文案表達力求精準、簡短，避免冗長修辭。

---

## 3. 資訊安全與隱私防護邊界 (Security & Privacy Boundaries)

### 3.1 零機敏資料外洩原則 (Zero Credential Leakage)
* 嚴格禁止將帳號密碼、OAuth Token、未遮罩之身分證字號或銀行帳號傳送至大型語言模型（LLM）API。
* 傳入 LLM 進行語意分析的欄位僅限於去識別化後的郵件主旨、寄件者網域與內文摘要。

### 3.2 憑證與設定檔隔離 (Credential Isolation)
* 以下檔案嚴禁加入 Git 版本控制（必須列於 `.gitignore`）：
  - `.env`
  - `credentials.json`
  - `token*.json`（包含 `token_gmail.json`, `token_hotmail.json`）
  - `rules*.yaml`（使用者私有規則檔）
  - `history/`

### 3.3 版本控制審批守則 (Push Approval Gate)
* AI Agent 可因應開發需要自主執行本地之 `git add` 與 `git commit`。
* **嚴格禁止自主執行 `git push`**：任何推送至遠端儲存庫之操作，必須先向使用者說明推送內容並取得明確授權後方可執行。

---

## 4. 模組架構

```text
mail-agent-plugin/
├── AGENTS.md                  # 外掛架構與工程開發規範
├── plugin.json                # Antigravity 外掛定義清單
├── README.md                  # 外掛使用手冊
├── requirements.txt           # 相依套件清單
├── core/                      # 跨服務核心模組
│   ├── auth_gmail.py          # Gmail OAuth 2.0 驗證與 Token 維護
│   ├── auth_microsoft.py      # Microsoft OAuth 2.0 驗證與 Token 維護
│   └── providers.py           # 信箱提供者抽象介面 (Gmail & Hotmail)
├── skills/                    # 技能定義目錄
│   └── promotion-cleaner/     # 促銷郵件分類技能
│       ├── SKILL.md           # 技能操作手冊
│       ├── clean_promotions.py# 分類執行腳本
│       ├── rollback.py        # 異動還原工具
│       ├── rules.gmail.example.yaml   # Gmail 規則範本
│       └── rules.hotmail.example.yaml # Hotmail 規則範本
└── tests/                     # 自動化測試
    └── test_providers.py
```
