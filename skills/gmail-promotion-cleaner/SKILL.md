---
name: gmail-promotion-cleaner
description: >-
  Use this skill when the user wants to categorize, filter, or clean up promotional marketing emails (EDMs) in Gmail,
  configure custom brand sub-labels in rules.yaml, preview email sorting decisions, or rollback previous email sorting actions.
---

# Gmail Promotion Cleaner Skill

A production-ready skill for AI Agents to intelligently classify, label, and archive promotional marketing emails (EDMs) in Gmail while preserving unread status and guaranteeing zero misclassification of critical notifications.

---

## 🎯 When to Use This Skill

Activate this skill when:
* The user complains of an inbox flooded with promotional EDM, coupons, newsletters, or marketing campaigns.
* The user asks to organize their Gmail unread emails into sub-labels (e.g., Costco, Coupang, Job alerts).
* The user requests a **dry run / preview** of email classification before executing any changes.
* The user asks to **rollback** or undo a previous email sorting run.
* The user wants to add a new brand filter or modify rules in `rules.yaml`.

---

## 🔒 Safety & Privacy Principles (Strict Rules)

1. **B-Mode Unread Preservation**:
   * Emails moved out of `INBOX` to custom labels **MUST keep their `UNREAD` state** (do NOT mark read unless explicitly requested).
2. **Whitelist Safeguards**:
   * **NEVER** archive or move:
     - Bank statements, credit card bills, utility receipts, or e-invoices.
     - 104/LinkedIn interview invitations or direct HR messages.
     - Security alerts, 2FA verification codes, password resets.
     - Personal and work communications.
   * If in doubt, **always default to SAFE (leave untouched in inbox)**.
3. **Deterministic Guardrails**:
   * Sub-labels MUST verify the sender's domain (e.g., sender must contain `104.com.tw` for 104, `costco` for Costco).

---

## ⚙️ Configuration (`rules.yaml`)

Custom sub-labels and whitelist descriptions are configured in `rules.yaml`:

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
    description: "酷澎商品推薦、關注商品熱銷與限時特賣信件"

  - id: "104_JOB"
    label_name: "104求職"
    domain_guardrail: "104.com.tw"
    description: "104 人力銀行的「職缺推薦、關注公司新職務通知、職涯電子報、行銷推薦」"

safe_rules:
  - "104 人力銀行的「面試邀請、HR 專人私訊、主動應徵之進度回覆」屬於極重要通知，一律歸類為 SAFE！"
  - "個人通訊、工作往來信件。"
  - "銀行綜合對帳單、信用卡帳單、電子發票開立通知。"
  - "密碼重設、帳戶安全性快訊、雙重驗證碼 (2FA)。"
```

To add a new brand (e.g., UberEats), simply append a new entry under `custom_rules`.

---

## 🛠️ Step-by-Step Execution Workflows

### 1. Preview Mode (Dry Run - Recommended First Step)
Always run preview first so the user can verify classification accuracy:

```bash
# Preview the latest 20 unread emails
python skills/gmail-promotion-cleaner/clean_promotions.py --limit 20
```

### 2. Live Execution (Execute Cleanup)
After user confirms preview decisions:

```bash
# Clean up up to 100 unread emails with live modification
python skills/gmail-promotion-cleaner/clean_promotions.py --live --limit 100
```
* Actions performed on promo emails:
  1. Add target sub-label (e.g. `MailAgent/廣告信/Costco`).
  2. Remove from `INBOX` (archive).
  3. Keep `UNREAD` badge intact.
  4. Write transaction log to `history/run_*.json`.

### 3. Rollback Mode (Undo / Revert Actions)
If the user wants to revert changes:

```bash
# View past run history logs
python skills/gmail-promotion-cleaner/rollback.py --list

# Preview the rollback of the last run
python skills/gmail-promotion-cleaner/rollback.py --last --dry-run

# Execute live rollback of the last run
python skills/gmail-promotion-cleaner/rollback.py --last
```

* **Human Override Protection**: If an email was manually moved to `TRASH` by the user, the rollback tool skips it and will not resurrect it.

---

## ☁️ Autonomous Cloud Execution (GitHub Actions)

When deployed with GitHub Actions (`.github/workflows/clean_promotions.yml`):
* Automatically runs 4 times daily (08:00, 12:00, 18:00, 23:00 UTC+8).
* Injects `secrets.GEMINI_API_KEY` and `secrets.GMAIL_TOKEN_JSON`.
* Renders a Markdown report in GitHub Step Summary.
* Automatically archives run transactions to GitHub Artifacts.
