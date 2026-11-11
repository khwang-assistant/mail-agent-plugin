import os
import sys
import glob
import json
import argparse

# Ensure plugin root is in sys.path for importing 'core'
PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

from core.providers import GmailProvider, HotmailProvider

HISTORY_DIR = "history"

def list_history_logs():
    """列出所有可用的歷史交易日誌"""
    if not os.path.exists(HISTORY_DIR):
        print("[INFO] 查無歷史紀錄。")
        return []
    logs = sorted(glob.glob(os.path.join(HISTORY_DIR, "run_*.json")), reverse=True)
    if not logs:
        print("[INFO] 查無歷史紀錄。")
        return []

    print("\n可用的歷史執行紀錄：")
    for idx, path in enumerate(logs, 1):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            ts = data.get('run_timestamp', '未知時間')
            provider_name = data.get('provider', 'GMAIL').upper()
            count = data.get('total_processed', 0)
            print(f"  [{idx}] {os.path.basename(path)} | 服務: {provider_name} | 時間: {ts} | 筆數: {count}")
        except Exception:
            print(f"  [{idx}] {os.path.basename(path)} (讀取失敗)")
    print()
    return logs

def rollback_single_log(log_path, dry_run=False):
    """執行特定日誌的還原作業，自動辨識信箱提供者 (Gmail / Hotmail)"""
    if not os.path.exists(log_path):
        print(f"[ERROR] 找不到日誌檔案：{log_path}")
        return

    with open(log_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    provider_name = data.get('provider', 'gmail').lower()
    actions = data.get('actions', [])
    ts = data.get('run_timestamp', '')

    print("=" * 72)
    mode_text = "[DRY-RUN]" if dry_run else "[LIVE]"
    print(f"還原歷史紀錄：{os.path.basename(log_path)}")
    print(f"服務提供者：{provider_name.upper()} | 時間: {ts} | 模式: {mode_text}")
    print("=" * 72)

    if provider_name == 'hotmail':
        provider = HotmailProvider()
    else:
        provider = GmailProvider()

    restored_count = 0

    for idx, act in enumerate(actions, 1):
        msg_id = act['message_id']
        dest_id = act.get('dest_id') or act.get('added_label_id')
        dest_name = act.get('dest_name') or act.get('added_label_name', '廣告信')
        subject = act.get('subject', '(無主旨)')[:40]

        try:
            action_desc = f"移回 INBOX 並移除分類 [{dest_name}]"

            if not dry_run:
                provider.restore_email(msg_id, dest_id)
                status_flag = "[RESTORED]"
            else:
                status_flag = "[DRY-RUN]"

            restored_count += 1
            print(f"[{idx}/{len(actions)}] {status_flag} 主旨：{subject}")
            print(f"       動作：{action_desc}")
            print("-" * 72)

        except Exception as e:
            print(f"[{idx}/{len(actions)}] [ERROR] 處理失敗 (ID: {msg_id})：{e}")
            print("-" * 72)

    print("\n" + "=" * 72)
    print("還原統計報告：")
    print(f"  服務提供者：{provider_name.upper()}")
    print(f"  總計處理信件：{len(actions)} 封")
    print(f"  成功還原至收件匣：{restored_count} 封")
    if dry_run:
        print("\n[說明] 當前為預覽模式，信箱未受任何異動。")
        print("       若欲執行實際還原，請移除 --dry-run 參數。")
    else:
        print("\n[完成] 還原執行完畢，信件已回復至收件匣。")
    print("=" * 72)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Mail Agent 郵件分類還原工具 (支援 Gmail & Hotmail)")
    parser.add_argument('--list', action='store_true', help="列出所有可用的歷史日誌")
    parser.add_argument('--last', action='store_true', help="還原最近一次的分類動作")
    parser.add_argument('--file', type=str, help="指定特定的歷史日誌檔案路徑進行還原")
    parser.add_argument('--all', action='store_true', help="還原所有的歷史紀錄")
    parser.add_argument('--dry-run', action='store_true', help="預覽還原動作，不實際變動信箱")
    args = parser.parse_args()

    logs = list_history_logs()

    if args.list:
        sys.exit(0)

    if args.last:
        if not logs:
            print("[ERROR] 查無可還原的歷史紀錄。")
            sys.exit(1)
        rollback_single_log(logs[0], dry_run=args.dry_run)
    elif args.file:
        rollback_single_log(args.file, dry_run=args.dry_run)
    elif args.all:
        if not logs:
            print("[ERROR] 查無可還原的歷史紀錄。")
            sys.exit(1)
        for log_p in logs:
            rollback_single_log(log_p, dry_run=args.dry_run)
    else:
        print("參數說明：")
        print("  --last     : 還原最近一次執行的整理動作")
        print("  --list     : 列出所有歷史紀錄")
        print("  --dry-run  : 搭配上述參數進行預覽，不實際變動信箱")
