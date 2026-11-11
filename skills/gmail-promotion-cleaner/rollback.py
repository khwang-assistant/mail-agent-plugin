import os
import sys
import glob
import json
import argparse
# Ensure plugin root is in sys.path for importing 'core'
PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

try:
    from core.auth_gmail import get_gmail_service
except ImportError:
    from auth_gmail import get_gmail_service

HISTORY_DIR = "history"

def list_history_logs():
    """列出所有可用的歷史交易日誌"""
    if not os.path.exists(HISTORY_DIR):
        print("📁 尚無任何執行歷史紀錄。")
        return []
    logs = sorted(glob.glob(os.path.join(HISTORY_DIR, "run_*.json")), reverse=True)
    if not logs:
        print("📁 尚無任何執行歷史紀錄。")
        return []
        
    print("\n📜 可用的歷史整理紀錄：")
    for idx, path in enumerate(logs, 1):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            ts = data.get('run_timestamp', '未知時間')
            count = data.get('total_processed', 0)
            print(f"  [{idx}] {os.path.basename(path)} | 執行時間: {ts} | 整理信件數: {count} 封")
        except Exception:
            print(f"  [{idx}] {os.path.basename(path)} (讀取失敗)")
    print()
    return logs

def rollback_single_log(service, log_path, dry_run=False):
    """執行特定日誌的還原作業，具備人為介入衝突檢測"""
    if not os.path.exists(log_path):
        print(f"❌ 找不到日誌檔案：{log_path}")
        return
        
    with open(log_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    actions = data.get('actions', [])
    ts = data.get('run_timestamp', '')
    print("=" * 72)
    mode_text = "🟢 [預覽還原 (Dry Run)]" if dry_run else "🔴 [正式還原 (LIVE)]"
    print(f"🔄 正在還原歷史紀錄：{os.path.basename(log_path)} (時間: {ts}) - {mode_text}")
    print("=" * 72)
    
    restored_count = 0
    skipped_trash_count = 0
    skipped_inbox_count = 0
    
    for idx, act in enumerate(actions, 1):
        msg_id = act['message_id']
        label_id = act['added_label_id']
        label_name = act['added_label_name']
        subject = act['subject'][:40]
        
        try:
            # 1. 查詢郵件當前最新狀態（Smart State Check）
            msg = service.users().messages().get(userId='me', id=msg_id, format='minimal').execute()
            current_labels = msg.get('labelIds', [])
            
            # 情況 A：信件已被使用者手動刪除進垃圾桶 ➡️ 跳過！絕不拉回
            if 'TRASH' in current_labels:
                skipped_trash_count += 1
                print(f"[{idx}/{len(actions)}] ⏭️ [略過] 主旨：{subject}")
                print(f"      原因：你已人為手動刪除至垃圾桶，尊重你的操作，不予拉回。")
                print("-" * 72)
                continue
                
            # 情況 B：信件是否已經在收件匣？
            is_already_in_inbox = 'INBOX' in current_labels
            
            # 還原動作：把 AI 貼上的標籤移除，並把信件搬回 INBOX
            remove_labels = [label_id] if label_id in current_labels else []
            add_labels = [] if is_already_in_inbox else ['INBOX']
            
            if is_already_in_inbox:
                skipped_inbox_count += 1
                action_desc = f"信件已在收件匣中，僅移除標籤【{label_name}】"
            else:
                action_desc = f"移回收件匣 (INBOX) 並移除標籤【{label_name}】"
                
            if not dry_run:
                if remove_labels or add_labels:
                    service.users().messages().modify(
                        userId='me',
                        id=msg_id,
                        body={
                            'addLabelIds': add_labels,
                            'removeLabelIds': remove_labels
                        }
                    ).execute()
                status_flag = "✅ [還原成功]"
            else:
                status_flag = "👀 [預計還原]"
                
            restored_count += 1
            print(f"[{idx}/{len(actions)}] {status_flag} 主旨：{subject}")
            print(f"      動作：{action_desc}")
            print("-" * 72)
            
        except Exception as e:
            print(f"[{idx}/{len(actions)}] ⚠️ 處理失敗 (ID: {msg_id})：{e}")
            print("-" * 72)
            
    print("\n" + "=" * 72)
    print("📊 還原統計報告：")
    print(f"   總計處理信件：{len(actions)} 封")
    print(f"   ✅ 成功還原至收件匣/撕標籤：{restored_count} 封")
    print(f"   🗑️ 因使用者已手動丟垃圾桶而略過：{skipped_trash_count} 封")
    print(f"   📬 原本就已在收件匣（未重複搬移）：{skipped_inbox_count} 封")
    if dry_run:
        print("\n💡 以上為【預覽還原模式】，未實際修改 Gmail。")
        print("   若要真正執行還原，請去掉 --dry-run 參數！")
    else:
        print("\n🎉 還原已全數執行完畢！信件已回到原始狀態。")
    print("=" * 72)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Gmail 整理一鍵還原工具 (Rollback Tool)")
    parser.add_argument('--list', action='store_true', help="列出所有可用的整理歷史日誌")
    parser.add_argument('--last', action='store_true', help="還原最近一次的整理動作")
    parser.add_argument('--file', type=str, help="指定特定的歷史日誌檔案路徑進行還原")
    parser.add_argument('--all', action='store_true', help="還原所有的歷史整理紀錄")
    parser.add_argument('--dry-run', action='store_true', help="預覽還原動作，不實際變動信箱")
    args = parser.parse_args()
    
    logs = list_history_logs()
    
    if args.list:
        sys.exit(0)
        
    service = get_gmail_service()
    
    if args.last:
        if not logs:
            print("❌ 沒有可還原的歷史紀錄。")
            sys.exit(1)
        rollback_single_log(service, logs[0], dry_run=args.dry_run)
    elif args.file:
        rollback_single_log(service, args.file, dry_run=args.dry_run)
    elif args.all:
        if not logs:
            print("❌ 沒有可還原的歷史紀錄。")
            sys.exit(1)
        for log_p in logs:
            rollback_single_log(service, log_p, dry_run=args.dry_run)
    else:
        print("💡 請提供還原參數：")
        print("   --last     : 還原最近一次執行的整理")
        print("   --list     : 列出所有歷史紀錄")
        print("   --dry-run  : 搭配上述參數進行預覽，不實際更動信箱")
