#!/usr/bin/env python3
"""Health Check Scheduler - Monitor service health 24/7"""

import requests
import schedule
import time
import sqlite3
from datetime import datetime, timedelta

HEALTH_CHECK_ENDPOINTS = {
    "API": "http://localhost:8000/health",
    "Database": "http://localhost:5432",
    "Cache": "http://localhost:6379",
    "WebServer": "http://localhost:80/health",
}

SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
CHECK_INTERVAL = 5
TIMEOUT = 5
DB_FILE = "health_checks.db"

def init_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS health_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL,
            status TEXT NOT NULL,
            response_time_ms INTEGER,
            error_message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def log_health_check(service_name, status, response_time_ms=0, error_message=None):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO health_checks 
            (service_name, status, response_time_ms, error_message)
            VALUES (?, ?, ?, ?)
        """, (service_name, status, response_time_ms, error_message))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[ERROR] Failed to log health check: {str(e)}")

def get_service_status(service_name, url):
    try:
        start_time = time.time()
        response = requests.get(url, timeout=TIMEOUT)
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            return "UP", response_time, None
        else:
            return "DOWN", response_time, f"HTTP {response.status_code}"
    except requests.exceptions.Timeout:
        return "DOWN", TIMEOUT * 1000, "Timeout"
    except requests.exceptions.ConnectionError:
        return "DOWN", 0, "Connection refused"
    except Exception as e:
        return "DOWN", 0, str(e)

def send_slack_alert(service_name, status, details):
    try:
        color = "#00CC00" if status == "UP" else "#FF0000"
        emoji = "✅" if status == "UP" else "🔴"
        
        payload = {
            "attachments": [{
                "color": color,
                "title": f"{emoji} {service_name} is {status}",
                "text": details,
                "fields": [{"title": "Time", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "short": True}]
            }]
        }
        requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
    except Exception as e:
        print(f"[ERROR] Failed to send Slack alert: {str(e)}")

def health_check_job():
    print(f"\n[{datetime.now()}] Running health checks...")
    for service_name, url in HEALTH_CHECK_ENDPOINTS.items():
        status, response_time, error = get_service_status(service_name, url)
        log_health_check(service_name, status, int(response_time), error)
        emoji = "✅" if status == "UP" else "❌"
        print(f"{emoji} {service_name}: {status} ({response_time:.0f}ms)")
        if status == "DOWN":
            send_slack_alert(service_name, "DOWN", f"Error: {error}")

def main():
    print(f"[{datetime.now()}] Starting Health Check Scheduler...")
    print(f"[{datetime.now()}] Monitoring {len(HEALTH_CHECK_ENDPOINTS)} services")
    
    init_database()
    schedule.every(CHECK_INTERVAL).minutes.do(health_check_job)
    health_check_job()
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        print(f"\n[{datetime.now()}] Stopping Health Check Scheduler")

if __name__ == "__main__":
    main()
