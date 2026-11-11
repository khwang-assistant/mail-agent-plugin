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

try:
    from core.auth_gmail import get_gmail_service
except ImportError:
    from auth_gmail import get_gmail_service

load_dotenv()

HISTORY_DIR = "history"
LABEL_CACHE = {}

def load_rules(config_path="rules.yaml"):
    """讀取 YAML 規則設定檔，若不存在則退回範本或預設值"""
    if not os.path.exists(config_path):
        skill_fallback = os.path.join(os.path.dirname(__file__), "rules.example.yaml")
        if os.path.exists("rules.example.yaml"):
            config_path = "rules.example.yaml"
        elif os.path.exists(skill_fallback):
            config_path = skill_fallback
        else:
            raise FileNotFoundError(f"找不到規則設定檔：{config_path}，請建立 rules.yaml")
            
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    labels_cfg = config.get("labels", {})
    parent_label = labels_cfg.get("parent", "MailAgent/廣告信")
    other_label = labels_cfg.get("other", f"{parent_label}/其他")

    custom_rules = []
    for r in config.get("custom_rules", []):
        sub_name = r.get("label_name", r.get("id"))
        full_label = f"{parent_label}/{sub_name}"
        custom_rules.append({
            "id": r.get("id", "").upper(),
            "label_name": sub_name,
            "full_label": full_label,
            "domain_guardrail": r.get("domain_guardrail", "").lower(),
            "description": r.get("description", "")
        })

    safe_rules = config.get("safe_rules", [
        "個人通訊、工作往來信件。",
        "銀行綜合對帳單、信用卡帳單、電子發票開立通知。",
        "密碼重設、帳戶安全性快訊、雙重驗證碼 (2FA)。"
    ])

    return {
        "parent_label": parent_label,
        "other_label": other_label,
        "custom_rules": custom_rules,
        "safe_rules": safe_rules,
        "rule_map": {r["id"]: r for r in custom_rules}
    }

def init_labels(service, rules_config):
    """初始化並建立所有需要的 Gmail 標籤"""
    results = service.users().labels().list(userId='me').execute()
    existing = {lbl['name']: lbl['id'] for lbl in results.get('labels', [])}
    
    needed = [rules_config["parent_label"], rules_config["other_label"]]
    for r in rules_config["custom_rules"]:
        needed.append(r["full_label"])

    for name in needed:
        if name in existing:
            LABEL_CACHE[name] = existing[name]
        else:
            body = {
                'name': name,
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }
            created = service.users().labels().create(userId='me', body=body).execute()
            LABEL_CACHE[name] = created['id']
            print(f"✨ 成功在 Gmail 建立標籤：【{name}】")

def fetch_unread_messages(service, max_total=100):
    """抓取收件匣中的未讀信件"""
    print("🔍 正在搜尋收件匣中的未讀信件 (label:INBOX is:unread)...")
    results = service.users().messages().list(
        userId='me',
        q='label:INBOX is:unread',
        maxResults=max_total
    ).execute()
    return results.get('messages', [])

def get_message_summary(service, msg_id):
    """取得單封信件的主旨、寄件人與摘要"""
    detail = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
    headers = detail.get('payload', {}).get('headers', [])
    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '(無主旨)')
    sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), '(未知寄件者)')
    snippet = detail.get('snippet', '')
    return {
        'id': msg_id,
        'subject': subject,
        'sender': sender,
        'snippet': snippet[:200]
    }

def batch_classify_emails(client, email_batch, rules_config, max_retries=3):
    """呼叫 Gemini 根據外部 rules.yaml 動態組合提示詞分類信件"""
    custom_desc_lines = []
    for r in rules_config["custom_rules"]:
        custom_desc_lines.append(f'   - 若為 {r["description"]}，sub_type 填 "{r["id"]}"')
    custom_desc_lines.append('   - 其餘一般電商特惠、折價券、行銷推廣、品牌 EDM、雙11促銷等，sub_type 填 "OTHER"')

    safe_desc_lines = []
    for s in rules_config["safe_rules"]:
        safe_desc_lines.append(f"   - {s}")
    safe_desc_lines.append("   - ⚠️ 若有任何疑慮，請一律歸類為 SAFE，絕不可誤判！")

    custom_text = "\n".join(custom_desc_lines)
    safe_text = "\n".join(safe_desc_lines)
    all_sub_types = [r["id"] for r in rules_config["custom_rules"]] + ["OTHER"]
    sub_type_options = " 或 ".join([f'"{x}"' for x in all_sub_types])

    prompt = f"""你是一個專業的郵件整理 AI。請分析以下這批郵件，逐一進行精準分類。

【分類準則】
1. PROMOTION (廣告促銷或定期推薦電子報):
{custom_text}

2. SAFE (安全保留，絕不移出收件匣):
{safe_text}

【待分析郵件列表】
{json.dumps(email_batch, ensure_ascii=False, indent=2)}

【輸出格式】
嚴格以 JSON 陣列回傳，每個項目格式如下：
[
  {{
    "id": "郵件ID",
    "category": "PROMOTION" 或 "SAFE",
    "sub_type": {sub_type_options}（若為 SAFE 則填 null）,
    "reason": "繁體中文簡述判定原因（15字以內）"
  }}
]
"""
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash-lite',
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            return json.loads(response.text)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(3 * (attempt + 1))
            else:
                print(f"⚠️ 批次分類出錯：{e}")
                return [{"id": em['id'], "category": "SAFE", "sub_type": None, "reason": "分析逾時保護"} for em in email_batch]

def write_github_step_summary(total_found, counts, processed_items, live_mode, rules_config):
    """若在 GitHub Actions 運行，將易讀之 Markdown 摘要渲染至執行首頁"""
    summary_file = os.getenv('GITHUB_STEP_SUMMARY')
    if not summary_file:
        return
    
    mode_badge = "🔴 正式執行模式 (LIVE)" if live_mode else "🟢 預覽模式 (DRY RUN)"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    lines = [
        f"## 📬 Mail Agent 整理結果報告 ({mode_badge})\n",
        f"- **執行時間**：`{now_str}`",
        f"- **總掃描未讀信件**：`{total_found}` 封\n",
    ]
    
    if total_found == 0:
        lines.append("> 🎉 **收件匣非常乾淨，目前沒有任何未讀信件！**\n")
    else:
        lines.extend([
            "### 📊 分類統計總覽",
            "| 類別 | 歸屬標籤 | 處理信件數 | 處置方式 |",
            "| :--- | :--- | :---: | :--- |"
        ])
        for r in rules_config["custom_rules"]:
            cnt = counts.get(r["id"], 0)
            lines.append(f"| 🏷️ **{r['label_name']}** | `{r['full_label']}` | **{cnt}** 封 | 貼標籤 + 移出收件匣 (維持未讀) |")
        
        other_cnt = counts.get("OTHER", 0)
        lines.append(f"| 🗑️ **其他促銷廣告** | `{rules_config['other_label']}` | **{other_cnt}** 封 | 貼標籤 + 移出收件匣 (維持未讀) |")
        lines.append(f"| 🛡️ **重要安全信件** | *(保留收件匣)* | **{counts['SAFE']}** 封 | **100% 安全保留（未更動）** |\n")
        
        if processed_items:
            lines.append("### 📝 本次廣告信分流明細清單")
            lines.append("| 標籤分類 | 主旨 | 寄件者 | AI 判定原因 |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for item in processed_items:
                clean_sub = item['subject'].replace('|', '&#124;').replace('\n', ' ')
                clean_snd = item['sender'].replace('|', '&#124;').replace('\n', ' ')
                clean_rsn = item['reason'].replace('|', '&#124;').replace('\n', ' ')
                lines.append(f"| `{item['label']}` | {clean_sub[:40]} | {clean_snd[:30]} | {clean_rsn} |")
            lines.append("")
        else:
            lines.append("> ✨ **本次掃描的所有未讀信件均為銀行帳單或重要安全通知，無任何廣告信需分流！**\n")
        
    try:
        with open(summary_file, 'a', encoding='utf-8') as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        print(f"⚠️ 寫入 GitHub Step Summary 失敗：{e}")

def run_cleaner(live_mode=False, batch_size=10, limit=100, config_path="rules.yaml"):
    mode_text = "🔴 正式執行模式 (LIVE - B模式: 貼標籤+移出收件匣+維持未讀)" if live_mode else "🟢 預覽模式 (DRY RUN - 不會修改任何信件)"
    print("=" * 72)
    print(f"🧹 Gmail 廣告信自動整理器 - {mode_text}")
    print("=" * 72)
    
    rules_config = load_rules(config_path)
    service = get_gmail_service()
    client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
    
    init_labels(service, rules_config)
    
    os.makedirs(HISTORY_DIR, exist_ok=True)
    messages = fetch_unread_messages(service, max_total=limit)
    total_found = len(messages)
    print(f"📬 共找到 {total_found} 封未讀信件待處理。\n")
    
    counts = {r["id"]: 0 for r in rules_config["custom_rules"]}
    counts["OTHER"] = 0
    counts["SAFE"] = 0
    
    if total_found == 0:
        print("🎉 收件匣中已經沒有任何未讀信件！")
        write_github_step_summary(0, counts, [], live_mode, rules_config)
        return
        
    transaction_records = []
    summary_items = []
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    
    for i in range(0, total_found, batch_size):
        chunk_ids = messages[i:i + batch_size]
        print(f"⏳ 正在讀取第 {i + 1} ~ {min(i + batch_size, total_found)} 封信件細節...")
        
        email_batch = [get_message_summary(service, m['id']) for m in chunk_ids]
        classified_results = batch_classify_emails(client, email_batch, rules_config)
        
        res_map = {item['id']: item for item in classified_results}
        for em in email_batch:
            res = res_map.get(em['id'], {'category': 'SAFE', 'sub_type': None, 'reason': '預設保護'})
            cat = res.get('category', 'SAFE')
            sub = (res.get('sub_type') or 'OTHER').upper()
            reason = res.get('reason', '')
            
            if cat == 'PROMOTION':
                # 動態物理防呆 (Deterministic Guardrail)：比對 rules.yaml 定義的 domain_guardrail
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
                    target_label_name = rules_config["rule_map"][sub]["full_label"]
                else:
                    target_label_name = rules_config["other_label"]
                    
                target_label_id = LABEL_CACHE[target_label_name]
                prefix = f"🏷️ [{target_label_name}]"
                action_text = f"貼上標籤並移出收件匣 (保持未讀)"
                
                summary_items.append({
                    'label': target_label_name,
                    'subject': em['subject'],
                    'sender': em['sender'],
                    'reason': reason
                })

                if live_mode:
                    service.users().messages().modify(
                        userId='me',
                        id=em['id'],
                        body={
                            'addLabelIds': [target_label_id],
                            'removeLabelIds': ['INBOX']
                        }
                    ).execute()
                    
                    transaction_records.append({
                        'message_id': em['id'],
                        'subject': em['subject'],
                        'sender': em['sender'],
                        'added_label_id': target_label_id,
                        'added_label_name': target_label_name,
                        'removed_label_ids': ['INBOX'],
                        'kept_unread': True,
                        'processed_at': datetime.now().isoformat()
                    })
                    status_flag = "✅ [已整理]"
                else:
                    status_flag = "👀 [預覽處置]"
            else:
                counts['SAFE'] += 1
                prefix = "🛡️ [安全保留]"
                action_text = "保留在收件匣（保持未讀），不做任何變動"
                status_flag = "✨ [未更動]"
                
            print(f"{status_flag} {prefix} 主旨：{em['subject'][:45]}")
            print(f"      寄件者：{em['sender'][:45]}")
            print(f"      判定：{reason} ➡️ {action_text}")
            print("-" * 72)
            
        time.sleep(1.5)
        
    if live_mode:
        os.makedirs(HISTORY_DIR, exist_ok=True)
        log_path = os.path.join(HISTORY_DIR, f"run_{run_timestamp}.json")
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump({
                'run_timestamp': run_timestamp,
                'total_scanned': total_found,
                'total_processed': len(transaction_records),
                'counts': counts,
                'actions': transaction_records
            }, f, ensure_ascii=False, indent=2)
        print(f"\n💾 異動交易日誌已存檔至：{log_path} (供日後 rollback 精準復原使用)")
        
    # 寫入 GitHub Actions 網頁視覺化報告
    write_github_step_summary(total_found, counts, summary_items, live_mode, rules_config)

    print("\n" + "=" * 72)
    print("📊 執行統計總結：")
    print(f"   總檢查信件數：{total_found} 封")
    for r in rules_config["custom_rules"]:
        print(f"   🏷️ {r['label_name']}：{counts[r['id']]} 封")
    print(f"   🗑️ 其他促銷廣告：{counts['OTHER']} 封")
    print(f"   🛡️ 重要安全信件：{counts['SAFE']} 封")
    if not live_mode:
        print("\n💡 以上為【預覽模式】，你的信箱未受到任何改動。")
        print("   若確認無誤，請通知我執行正式整理 (LIVE)！")
    else:
        print(f"\n🎉 正式整理完成！共整理了 {len(transaction_records)} 封廣告信。")
        print("   若日後想復原，只需執行: python rollback.py --last")
    print("=" * 72)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Gmail 廣告信自動整理器 (Config-Driven / rules.yaml)")
    parser.add_argument('--live', action='store_true', help="正式執行清理（若未加上此參數則為預覽模式）")
    parser.add_argument('--limit', type=int, default=100, help="最多處理的未讀信件數（預設 100）")
    parser.add_argument('--config', type=str, default="rules.yaml", help="指定規則設定檔路徑 (預設 rules.yaml)")
    args = parser.parse_args()
    
    run_cleaner(live_mode=args.live, limit=args.limit, config_path=args.config)
