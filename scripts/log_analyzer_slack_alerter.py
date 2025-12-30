#!/usr/bin/env python3
"""
Log Analyzer & Slack Alerter
Real-time error detection in application logs with instant Slack notifications.

Usage:
    python log_analyzer_slack_alerter.py

Configuration:
    Set LOG_FILE_PATH and SLACK_WEBHOOK_URL below
"""

import re
import requests
import time
import sys
from datetime import datetime
from pathlib import Path

# ============================================================================
# CONFIGURATION (Update these for your environment)
# ============================================================================

LOG_FILE_PATH = "/var/log/application.log"  # Change to your log file
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
CHECK_INTERVAL = 5  # Check logs every 5 seconds

# Error patterns to detect (regex)
ERROR_PATTERNS = {
    "CRITICAL": r"(CRITICAL|FATAL|PANIC|EMERGENCY)",
    "ERROR": r"(ERROR|FAIL|FAILURE)",
    "WARNING": r"(WARNING|WARN)",
    "DB_CONNECTION": r"(database connection|connection refused|connection timeout)",
    "API_TIMEOUT": r"(timeout|timed out|request timeout)",
    "MEMORY": r"(out of memory|memory error|OOM|heap space)",
    "DISK_FULL": r"(disk full|no space left|disk space)",
}

# ============================================================================
# COLOR CODES FOR SLACK
# ============================================================================

SEVERITY_COLORS = {
    "CRITICAL": "#FF0000",
    "ERROR": "#FF6600",
    "WARNING": "#FFFF00",
    "DB_CONNECTION": "#FF3333",
    "API_TIMEOUT": "#FF9933",
    "MEMORY": "#CC0000",
    "DISK_FULL": "#990000",
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def send_slack_alert(severity, message, error_details):
    """Send error alert to Slack"""
    try:
        payload = {
            "attachments": [
                {
                    "color": SEVERITY_COLORS.get(severity, "#CCCCCC"),
                    "title": f"🚨 {severity} Alert",
                    "text": message,
                    "fields": [
                        {
                            "title": "Error Details",
                            "value": error_details[:500],
                            "short": False
                        },
                        {
                            "title": "Timestamp",
                            "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "short": True
                        },
                        {
                            "title": "Host",
                            "value": "Production",
                            "short": True
                        }
                    ]
                }
            ]
        }
        
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        
        if response.status_code != 200:
            print(f"[{datetime.now()}] Failed to send Slack alert: {response.status_code}")
        else:
            print(f"[{datetime.now()}] ✓ Slack alert sent: {severity}")
            
    except Exception as e:
        print(f"[{datetime.now()}] Error sending Slack alert: {str(e)}")

def read_log_file(file_path):
    """Read new lines from log file"""
    try:
        if not Path(file_path).exists():
            print(f"[{datetime.now()}] ERROR: Log file not found: {file_path}")
            return []
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        return lines
        
    except Exception as e:
        print(f"[{datetime.now()}] Error reading log file: {str(e)}")
        return []

def analyze_logs(lines, last_position=0):
    """Analyze log lines for errors"""
    new_errors = []
    
    for line_num, line in enumerate(lines[last_position:], start=last_position):
        for severity, pattern in ERROR_PATTERNS.items():
            if re.search(pattern, line, re.IGNORECASE):
                new_errors.append({
                    "severity": severity,
                    "line": line.strip(),
                    "line_num": line_num,
                    "timestamp": datetime.now()
                })
                break
    
    return new_errors

def main():
    """Main monitoring loop"""
    print(f"[{datetime.now()}] Starting Log Analyzer...")
    print(f"[{datetime.now()}] Monitoring: {LOG_FILE_PATH}")
    print(f"[{datetime.now()}] Check interval: {CHECK_INTERVAL} seconds")
    print(f"[{datetime.now()}] Press Ctrl+C to stop\n")
    
    if not SLACK_WEBHOOK_URL or SLACK_WEBHOOK_URL == "https://hooks.slack.com/services/YOUR/WEBHOOK/URL":
        print("[WARNING] SLACK_WEBHOOK_URL not configured. Alerts will not be sent.")
        print("[WARNING] Get webhook URL from: https://api.slack.com/apps\n")
    
    last_position = 0
    error_count = 0
    
    try:
        while True:
            lines = read_log_file(LOG_FILE_PATH)
            
            if len(lines) > last_position:
                new_errors = analyze_logs(lines, last_position)
                
                if new_errors:
                    for error in new_errors:
                        error_count += 1
                        
                        print(f"[{error['timestamp']}] {error['severity']} (Line {error['line_num']})")
                        print(f"  → {error['line'][:80]}\n")
                        
                        send_slack_alert(
                            error['severity'],
                            f"Detected {error['severity']} in production logs",
                            error['line']
                        )
                
                last_position = len(lines)
            
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print(f"\n[{datetime.now()}] Stopping Log Analyzer")
        print(f"[{datetime.now()}] Total errors detected: {error_count}")
        sys.exit(0)
    except Exception as e:
        print(f"[{datetime.now()}] Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
