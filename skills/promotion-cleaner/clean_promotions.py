import os
import sys
import json
import time
import argparse
from datetime import datetime
import yaml
from dotenv import load_dotenv
from google import genai

# Ensure plugin root is in sys.path for importing 'core'
PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

from core.providers import BaseEmailProvider, GmailProvider, HotmailProvider

load_dotenv()

HISTORY_DIR = "history"
LABEL_CACHE = {}

def load_rules(provider_name: str, config_path: str = None):
    """讀取 YAML 規則設定檔，依序尋找指定檔、rules.{provider}.yaml 或 rules.yaml"""
    resolved_path = None
    if config_path and os.path.exists(config_path):
        resolved_path = config_path
    elif os.path.exists(f"rules.{provider_name}.yaml"):
        resolved_path = f"rules.{provider_name}.yaml"
    elif os.path.exists("rules.yaml"):
        resolved_path = "rules.yaml"
    else:
        skill_fallback = os.path.join(os.path.dirname(__file__), f"rules.{provider_name}.example.yaml")
        general_fallback = os.path.join(os.path.dirname(__file__), "rules.example.yaml")
        if os.path.exists(skill_fallback):
            resolved_path = skill_fallback
        elif os.path.exists(general_fallback):
            resolved_path = general_fallback

    config = {}
    if resolved_path and os.path.exists(resolved_path):
        print(f"[CONFIG] 已載入規則設定檔：{resolved_path}")
        with open(resolved_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    else:
        print("[CONFIG] 使用預設安全與分類規則。")

    labels_cfg = config.get("labels", {})
    parent_label = labels_cfg.get("parent", "MailAgent/廣告信" if provider_name == "gmail" else "MailAgent - 廣告信")
    other_label = labels_cfg.get("other", f"{parent_label}/其他" if provider_name == "gmail" else f"{parent_label} - 其他")

    custom_rules = []
    for r in config.get("custom_rules", []):
        sub_name = r.get("label_name", r.get("id"))
        separator = "/" if provider_name == "gmail" else " - "
        full_label = f"{parent_label}{separator}{sub_name}"
        custom_rules.append({
            "id": r.get("id", "").upper(),
            "label_name": sub_name,
            "full_label": full_label,
            "domain_guardrail": r.get("domain_guardrail", "").lower(),
            "description": r.get("description", "")
        })

    safe_rules = config.get("safe_rules", [
        "個人通訊、工作往來信件。",
        "銀行綜合對帳單、信用卡消費帳單、電子發票開立通知、繳費收據。",
        "密碼重設、帳戶安全性快訊、雙步驟驗證碼 (2FA)、備援信箱通知。"
    ])

    rule_map = {r["id"]: r for r in custom_rules}

    return {
        "parent_label": parent_label,
        "other_label": other_label,
        "custom_rules": custom_rules,
        "safe_rules": safe_rules,
        "rule_map": rule_map,
        "config_file": resolved_path
    }

def batch_classify_emails(client, emails, rules_config):
    """使用 Gemini 批次判定信件類別"""
    if not emails:
        return []

    custom_types_prompt = ""
    for r in rules_config["custom_rules"]:
        custom_types_prompt += f'- "{r["id"]}": {r["description"]}\n'

    safe_rules_prompt = "\n".join([f"- {s}" for s in rules_config["safe_rules"]])

    prompt = f"""你是一個精準的郵件過濾安全專家。你的任務是從給定的郵件批次中，辨識出「行銷廣告促銷信（EDM）」並貼上對應的標籤，同時「絕對不可誤封存」任何重要系統通知或個人往來信件。

### 分類標籤選項：
1. 若判定為行銷廣告或促銷活動，category 填 "PROMOTION"，sub_type 請依照以下規則嚴格選擇：
{custom_types_prompt}
- "OTHER": 其他一般電商購物促銷、品牌電子報、促銷 EDM。

2. 若為以下重要信件，category 一律填 "SAFE"，sub_type 填 null：
{safe_rules_prompt}

請分析以下信件列表：
"""

    for idx, em in enumerate(emails):
        prompt += f"""
---
信件編號 [{idx}]:
ID: {em['id']}
主旨: {em['subject']}
寄件者: {em['sender']}
內文摘要: {em['snippet']}
"""

    prompt += """
請僅輸出標準 JSON 格式（包含一個陣列 items），每個物件包含：
- "id": 信件 ID (字串)
- "category": "PROMOTION" 或 "SAFE"
- "sub_type": 對應標籤代碼 (大寫字串，若 SAFE 則為 null)
- "reason": 簡要繁體中文判定理由 (20字以內)

範例格式：
{
  "items": [
    {"id": "...", "category": "PROMOTION", "sub_type": "OTHER", "reason": "促銷推薦通知"},
    {"id": "...", "category": "SAFE", "sub_type": null, "reason": "系統安全性警示"}
  ]
}
"""

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash-lite',
                contents=prompt,
                config={
                    'response_mime_type': 'application/json',
                    'temperature': 0.1,
                }
            )
            data = json.loads(response.text)
            return data.get("items", [])
        except Exception as e:
            if attempt == 2:
                print(f"[WARN] Gemini API 分類失敗: {e}，該批次執行安全保留。")
                return [{"id": em['id'], "category": "SAFE", "sub_type": None, "reason": "API 異常回退安全保護"} for em in emails]
            time.sleep(2)

def write_github_step_summary(provider_name, total_found, counts, processed_items, live_mode, rules_config):
    """若在 GitHub Actions 運行，將易讀之 Markdown 摘要渲染至執行首頁"""
    summary_file = os.getenv('GITHUB_STEP_SUMMARY')
    if not summary_file:
        return

    mode_badge = "正式執行模式 (LIVE)" if live_mode else "預覽模式 (DRY RUN)"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"## Mail Agent 郵件分類處理報告 ({mode_badge})\n",
        f"- **信箱服務提供者**：`{provider_name.upper()}`",
        f"- **執行時間**：`{now_str}`",
        f"- **總掃描未讀信件**：`{total_found}` 封\n",
    ]

    if total_found == 0:
        lines.append("> 收件匣無待處理之未讀信件。\n")
    else:
        lines.extend([
            "### 分類統計摘要",
            "| 類別 | 目標標籤 / 資料夾 | 處理信件數 | 處置方式 |",
            "| :--- | :--- | :---: | :--- |"
        ])
        for r in rules_config["custom_rules"]:
            cnt = counts.get(r["id"], 0)
            lines.append(f"| 分類: **{r['label_name']}** | `{r['full_label']}` | **{cnt}** 封 | 移出收件匣並保留未讀狀態 |")

        other_cnt = counts.get("OTHER", 0)
        lines.append(f"| **其他促銷郵件** | `{rules_config['other_label']}` | **{other_cnt}** 封 | 移出收件匣並保留未讀狀態 |")
        lines.append(f"| **安全保留信件** | *(收件匣)* | **{counts['SAFE']}** 封 | **保留於收件匣（未更動）** |\n")

        if processed_items:
            lines.append("### 處理明細清單")
            lines.append("| 目標分類 | 主旨 | 寄件者 | 判定原因 |",)
            lines.append("| :--- | :--- | :--- | :--- |")
            for item in processed_items:
                clean_sub = item['subject'].replace('|', '&#124;').replace('\n', ' ')
                clean_snd = item['sender'].replace('|', '&#124;').replace('\n', ' ')
                clean_rsn = item['reason'].replace('|', '&#124;').replace('\n', ' ')
                lines.append(f"| `{item['label']}` | {clean_sub[:40]} | {clean_snd[:30]} | {clean_rsn} |")
            lines.append("")
        else:
            lines.append("> 本次掃描之未讀信件均屬重要系統或金融通知，無符合規則之促銷信件。\n")

    try:
        with open(summary_file, 'a', encoding='utf-8') as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        print(f"[WARN] 寫入 GitHub Step Summary 失敗：{e}")

def run_cleaner(provider_name: str, live_mode: bool = False, batch_size: int = 10, limit: int = 100, config_path: str = None):
    provider_name = provider_name.lower()
    mode_text = "正式執行模式 (LIVE: 歸檔並保留未讀狀態)" if live_mode else "預覽模式 (DRY RUN: 僅分析不變更狀態)"
    print("=" * 72)
    print(f"Mail Agent [{provider_name.upper()}] 郵件分類處理器 - {mode_text}")
    print("=" * 72)

    if provider_name == "gmail":
        provider = GmailProvider()
    elif provider_name == "hotmail":
        provider = HotmailProvider()
    else:
        print(f"[ERROR] 不支援的信箱 provider '{provider_name}'。目前僅支援：gmail, hotmail。")
        sys.exit(1)

    rules_config = load_rules(provider_name, config_path)
    client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

    for r in rules_config["custom_rules"]:
        dest_name = r["full_label"]
        LABEL_CACHE[dest_name] = provider.get_or_create_destination(dest_name)
    LABEL_CACHE[rules_config["other_label"]] = provider.get_or_create_destination(rules_config["other_label"])

    os.makedirs(HISTORY_DIR, exist_ok=True)
    print(f"[INFO] 正在檢索 {provider_name.upper()} 收件匣未讀信件...")
    messages = provider.fetch_unread_emails(limit=limit)
    total_found = len(messages)
    print(f"[INFO] 共檢索到 {total_found} 封未讀信件待處理。\n")

    counts = {r["id"]: 0 for r in rules_config["custom_rules"]}
    counts["OTHER"] = 0
    counts["SAFE"] = 0

    if total_found == 0:
        print("[INFO] 收件匣中無待處理之未讀信件。")
        write_github_step_summary(provider_name, 0, counts, [], live_mode, rules_config)
        return

    transaction_records = []
    summary_items = []
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    for i in range(0, total_found, batch_size):
        chunk = messages[i:i + batch_size]
        print(f"[INFO] 正在處理第 {i + 1} ~ {min(i + batch_size, total_found)} 封信件批次...")

        classified_results = batch_classify_emails(client, chunk, rules_config)
        res_map = {item['id']: item for item in classified_results}

        for em in chunk:
            res = res_map.get(em['id'], {'category': 'SAFE', 'sub_type': None, 'reason': '預設保護'})
            cat = res.get('category', 'SAFE')
            sub = (res.get('sub_type') or 'OTHER').upper()
            reason = res.get('reason', '')

            if cat == 'PROMOTION':
                rule_obj = rules_config["rule_map"].get(sub)
                if rule_obj:
                    guardrail = rule_obj.get("domain_guardrail")
                    sender_lower = em['sender'].lower()
                    if guardrail and guardrail not in sender_lower:
                        sub = 'OTHER'
                else:
                    sub = 'OTHER'

                counts[sub] = counts.get(sub, 0) + 1

                if sub in rules_config["rule_map"]:
                    target_dest_name = rules_config["rule_map"][sub]["full_label"]
                else:
                    target_dest_name = rules_config["other_label"]

                target_dest_id = LABEL_CACHE[target_dest_name]
                action_text = "歸檔至指定分類並移出收件匣（保留未讀狀態）"

                summary_items.append({
                    'label': target_dest_name,
                    'subject': em['subject'],
                    'sender': em['sender'],
                    'reason': reason
                })

                if live_mode:
                    provider.move_email(em['id'], target_dest_id)
                    transaction_records.append({
                        'provider': provider_name,
                        'message_id': em['id'],
                        'subject': em['subject'],
                        'sender': em['sender'],
                        'dest_id': target_dest_id,
                        'dest_name': target_dest_name,
                        'kept_unread': True,
                        'processed_at': datetime.now().isoformat()
                    })
                    status_flag = "[LIVE]"
                else:
                    status_flag = "[DRY-RUN]"

                print(f"{status_flag} [{target_dest_name}] 主旨：{em['subject'][:45]}")
                print(f"       寄件者：{em['sender'][:45]}")
                print(f"       判定：{reason} -> {action_text}")
                print("-" * 72)
            else:
                counts['SAFE'] += 1
                status_flag = "[LIVE]" if live_mode else "[DRY-RUN]"
                print(f"{status_flag} [SAFE] 主旨：{em['subject'][:45]}")
                print(f"       寄件者：{em['sender'][:45]}")
                print(f"       判定：{reason} -> 保留於收件匣（未更動）")
                print("-" * 72)

        time.sleep(1.5)

    if live_mode:
        log_path = os.path.join(HISTORY_DIR, f"run_{run_timestamp}.json")
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump({
                'provider': provider_name,
                'run_timestamp': run_timestamp,
                'total_scanned': total_found,
                'total_processed': len(transaction_records),
                'counts': counts,
                'actions': transaction_records
            }, f, ensure_ascii=False, indent=2)
        print(f"\n[LOG] 異動紀錄已存檔至：{log_path}")

    write_github_step_summary(provider_name, total_found, counts, summary_items, live_mode, rules_config)

    print("\n" + "=" * 72)
    print("執行統計摘要：")
    print(f"  服務提供者：{provider_name.upper()}")
    print(f"  總檢查信件數：{total_found} 封")
    for r in rules_config["custom_rules"]:
        print(f"  分類 [{r['label_name']}]：{counts[r['id']]} 封")
    print(f"  其他促銷郵件：{counts['OTHER']} 封")
    print(f"  安全保留信件：{counts['SAFE']} 封")
    if not live_mode:
        print("\n[說明] 當前為預覽模式，信箱未受任何異動。")
        print("       確認無誤後，可加上 --live 參數執行正式歸檔。")
    else:
        print(f"\n[完成] 處理完成，共歸檔 {len(transaction_records)} 封促銷郵件。")
        print("       如需還原，可執行: python rollback.py --last")
    print("=" * 72)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Mail Agent 郵件分類處理器 (支援 Gmail & Hotmail)")
    parser.add_argument('--provider', type=str, choices=['gmail', 'hotmail'], help="指定信箱服務提供者 (gmail 或 hotmail)")
    parser.add_argument('--live', action='store_true', help="正式執行清理（若未加上此參數則為預覽模式）")
    parser.add_argument('--limit', type=int, default=100, help="最多處理的未讀信件數（預設 100）")
    parser.add_argument('--config', type=str, default=None, help="指定規則設定檔路徑")
    args = parser.parse_args()

    provider = args.provider
    if not provider:
        if os.path.exists("rules.yaml"):
            try:
                with open("rules.yaml", "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                    provider = cfg.get("provider")
            except Exception:
                pass

    if not provider:
        print("\n[ERROR] 未指定信箱服務提供者！")
        print("請在指令中加入 --provider gmail 或 --provider hotmail（或於 rules.yaml 中指定 provider）。\n")
        sys.exit(1)

    run_cleaner(provider_name=provider, live_mode=args.live, limit=args.limit, config_path=args.config)
