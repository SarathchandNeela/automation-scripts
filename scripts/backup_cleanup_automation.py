#!/usr/bin/env python3
"""Automated Backup & Cleanup - Archive logs and manage disk space"""

import os
import gzip
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import argparse

LOG_DIR = "/var/log"
BACKUP_DIR = "/backups"
RETENTION_DAYS = 30
MIN_FREE_SPACE_GB = 5
DB_FILE = "backup_cleanup.db"

def init_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL,
            backup_file TEXT NOT NULL,
            size_bytes INTEGER,
            compressed_size_bytes INTEGER,
            compression_ratio REAL,
            backup_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def log_backup(source_file, backup_file, original_size, compressed_size):
    try:
        compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO backups 
            (source_file, backup_file, size_bytes, compressed_size_bytes, compression_ratio)
            VALUES (?, ?, ?, ?, ?)
        """, (source_file, backup_file, original_size, compressed_size, compression_ratio))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[ERROR] Failed to log backup: {str(e)}")

def backup_logs():
    print(f"\n[{datetime.now()}] Starting log backup...")
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    
    total_backed_up = 0
    total_compressed = 0
    
    try:
        log_dir = Path(LOG_DIR)
        for log_file in log_dir.glob("*.log"):
            if log_file.suffix == ".gz":
                continue
            
            date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{log_file.stem}_{date_str}.log.gz"
            backup_path = Path(BACKUP_DIR) / backup_name
            
            try:
                original_size = log_file.stat().st_size
                with open(log_file, 'rb') as f_in:
                    with gzip.open(backup_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                compressed_size = backup_path.stat().st_size
                log_backup(str(log_file), str(backup_path), original_size, compressed_size)
                
                total_backed_up += original_size
                total_compressed += compressed_size
                
                compression_ratio = (1 - compressed_size / original_size) * 100
                print(f"✓ Backed up: {log_file.name}")
                print(f"  Original: {original_size:,} bytes → Compressed: {compressed_size:,} bytes ({compression_ratio:.1f}% reduction)")
            except Exception as e:
                print(f"✗ Failed to backup {log_file.name}: {str(e)}")
        
        print(f"\n📊 Backup Summary:")
        print(f"  Total backed up: {total_backed_up:,} bytes")
        print(f"  Space saved: {total_backed_up - total_compressed:,} bytes")
    except Exception as e:
        print(f"[ERROR] Backup failed: {str(e)}")

def cleanup_old_backups():
    print(f"\n[{datetime.now()}] Starting cleanup of old backups...")
    cutoff_date = datetime.now() - timedelta(days=RETENTION_DAYS)
    total_freed = 0
    files_deleted = 0
    
    try:
        backup_dir = Path(BACKUP_DIR)
        for backup_file in backup_dir.glob("*.gz"):
            mod_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
            if mod_time < cutoff_date:
                try:
                    size = backup_file.stat().st_size
                    backup_file.unlink()
                    total_freed += size
                    files_deleted += 1
                    print(f"✓ Deleted: {backup_file.name} ({size:,} bytes)")
                except Exception as e:
                    print(f"✗ Failed to delete {backup_file.name}: {str(e)}")
        
        print(f"\n🗑️  Cleanup Summary:")
        print(f"  Files deleted: {files_deleted}")
        print(f"  Space freed: {total_freed:,} bytes ({total_freed / 1024 / 1024 / 1024:.2f} GB)")
    except Exception as e:
        print(f"[ERROR] Cleanup failed: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Backup and cleanup automation")
    parser.add_argument("--backup", action="store_true", help="Run backup")
    parser.add_argument("--cleanup", action="store_true", help="Cleanup old backups")
    parser.add_argument("--all", action="store_true", help="Run backup + cleanup")
    
    args = parser.parse_args()
    init_database()
    
    if args.all or (not args.backup and not args.cleanup):
        backup_logs()
        cleanup_old_backups()
    else:
        if args.backup:
            backup_logs()
        if args.cleanup:
            cleanup_old_backups()

if __name__ == "__main__":
    main()
