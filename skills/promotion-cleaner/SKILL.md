---
name: promotion-cleaner
description: >-
  Use this skill when the user wants to categorize, filter, or clean up promotional marketing emails (EDMs) in Gmail or Hotmail/Outlook,
  configure custom brand sub-labels/folders in rules.gmail.yaml or rules.hotmail.yaml, preview email sorting decisions, or rollback previous email sorting actions.
---

# Promotion Cleaner Skill

A production-ready skill for AI Agents to intelligently classify, label, and archive promotional marketing emails (EDMs) in **Gmail** and **Hotmail/Outlook.com** while preserving unread status and guaranteeing zero misclassification of critical notifications.

---

## When to Use This Skill

Activate this skill when:
* The user needs to categorize promotional EDMs, newsletters, ecommerce offers, or marketing campaigns.
* The user asks to organize their Gmail (labels) or Hotmail/Outlook (folders) unread emails into sub-categories (e.g., Amazon, LinkedIn, UberEats).
* The user requests a dry-run preview of email classification before executing any changes.
* The user asks to rollback or undo a previous email sorting run.
* The user wants to add a new brand filter or modify rules in `rules.gmail.yaml` or `rules.hotmail.yaml`.

---

## Safety & Privacy Principles

1. **Mandatory `--provider` Parameter**:
   * Users MUST explicitly pass `--provider gmail` or `--provider hotmail` (or specify in rules configuration).
   * Implicit defaulting to any provider is strictly disallowed to prevent operations on unintended mailboxes.
2. **Unread Status Preservation**:
   * Emails moved out of `INBOX` to custom labels or folders MUST retain their `UNREAD` state (`isRead: false`).
3. **Whitelist Safeguards**:
   * NEVER archive or move:
     - Bank statements, credit card bills, utility receipts, or e-invoices.
     - Job interview invitations, recruiter communications.
     - Security alerts, 2FA verification codes, password resets, backup email alerts.
     - Personal and work communications.
   * If classification confidence is low, always default to SAFE (leave untouched in inbox).
4. **Deterministic Guardrails**:
   * Custom brand rules verify the sender's domain (e.g., sender must contain `amazon` for Amazon, `linkedin.com` for LinkedIn).

---

## Configuration (`rules.gmail.yaml` & `rules.hotmail.yaml`)

Configuration is separated by provider to keep rules isolated:

### 1. Gmail Configuration (`rules.gmail.yaml`)
```yaml
provider: "gmail"

labels:
  parent: "MailAgent/廣告信"
  other: "MailAgent/廣告信/其他"

custom_rules:
  - id: "AMAZON"
    label_name: "Amazon"
    domain_guardrail: "amazon"
    description: "Amazon 線上購物促銷、今日特惠與包裹行銷推薦信件"

  - id: "LINKEDIN"
    label_name: "LinkedIn"
    domain_guardrail: "linkedin.com"
    description: "LinkedIn 人脈動態、精選職缺推薦與職場每週精選電子報"

  - id: "UBEREATS"
    label_name: "UberEats"
    domain_guardrail: "ubereats"
    description: "UberEats 美食外送優惠券、限時免運折扣與生鮮推廣信件"

safe_rules:
  - "個人通訊、工作往來信件。"
  - "銀行綜合對帳單、信用卡帳單、水電瓦斯繳費通知、電子發票開立通知。"
  - "密碼重設、帳戶安全性快訊、雙步驟驗證碼 (2FA)。"
```

### 2. Hotmail / Outlook Configuration (`rules.hotmail.yaml`)
```yaml
provider: "hotmail"

labels:
  parent: "MailAgent - 廣告信"
  other: "MailAgent - 廣告信 - 其他"

# 若留空 []，則所有行銷促銷信件均會安全歸類於「其他」資料夾
custom_rules:
  - id: "AMAZON"
    label_name: "Amazon"
    domain_guardrail: "amazon"
    description: "Amazon 線上購物促銷、今日特惠與包裹行銷推薦信件"

  - id: "SUBSTACK"
    label_name: "Substack"
    domain_guardrail: "substack.com"
    description: "Substack 訂閱型知識電子報、創作者最新文章推播"

safe_rules:
  - "微軟帳戶安全性警示、密碼重設、單次登入代碼、備援信箱驗證通知。"
  - "Microsoft 官方電子發票、各銀行綜合對帳單、信用卡消費帳單。"
  - "個人通訊、工作往來信件。"
```

---

## Execution Workflows

### 1. Preview Mode (Dry Run)
Execute preview to verify classification accuracy before applying modifications:

```bash
# Preview Gmail unread emails
python skills/promotion-cleaner/clean_promotions.py --provider gmail --limit 20

# Preview Hotmail unread emails
python skills/promotion-cleaner/clean_promotions.py --provider hotmail --limit 20
```

### 2. Live Execution
Execute live modification after confirming preview decisions:

```bash
# Process Gmail unread emails
python skills/promotion-cleaner/clean_promotions.py --provider gmail --live --limit 50

# Process Hotmail unread emails
python skills/promotion-cleaner/clean_promotions.py --provider hotmail --live --limit 50
```
* Actions performed on promotional emails:
  1. Add target sub-label (Gmail) or move to target folder (Hotmail).
  2. Remove from `INBOX` (archive).
  3. Keep `UNREAD` badge intact.
  4. Write transaction log to `history/run_*.json`.

### 3. Rollback Mode
Revert previous actions using logged transaction data:

```bash
# View past run history logs (auto-detects Gmail vs Hotmail)
python skills/promotion-cleaner/rollback.py --list

# Preview the rollback of the last run
python skills/promotion-cleaner/rollback.py --last --dry-run

# Execute live rollback of the last run
python skills/promotion-cleaner/rollback.py --last
```

---

## Autonomous Cloud Execution (GitHub Actions)

When deployed with GitHub Actions (`.github/workflows/clean_promotions.yml`):
* Automatically runs 4 times daily (08:00, 12:00, 18:00, 23:00 UTC+8).
* Injects `secrets.GEMINI_API_KEY` and `secrets.GMAIL_TOKEN_JSON`.
* Renders a Markdown report in GitHub Step Summary with provider badges.
* Automatically archives run transactions to GitHub Artifacts.
