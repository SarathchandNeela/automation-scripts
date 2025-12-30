#!/usr/bin/env python3
"""Incident Response Automation - Auto-detect and recover from failures"""

import subprocess
import requests
import time
import sqlite3
from datetime import datetime
import logging

SERVICES_TO_MONITOR = {
    "nginx": "/usr/sbin/nginx -t",
    "postgresql": "pg_isready -h localhost",
    "redis": "redis-cli ping",
    "application": "curl -s http://localhost:8000/health",
}

RECOVERY_COMMANDS = {
    "nginx": "sudo systemctl restart nginx",
    "postgresql": "sudo systemctl restart postgresql",
    "redis": "sudo systemctl restart redis-server",
    "application": "sudo systemctl restart application",
}

SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
CHECK_INTERVAL = 30
DB_FILE = "incidents.db"

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[logging.FileHandler('incident_response.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def init_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL,
            incident_type TEXT NOT NULL,
            start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            end_time DATETIME,
            recovery_attempts INTEGER,
            recovery_successful BOOLEAN,
            details TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_incident(service_name, incident_type, details):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO incidents 
            (service_name, incident_type, recovery_successful, details)
            VALUES (?, ?, ?, ?)
        """, (service_name, incident_type, False, details))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log incident: {str(e)}")

def check_service_health(service_name, check_command):
    try:
        result = subprocess.run(check_command, shell=True, capture_output=True, timeout=5, text=True)
        if result.returncode == 0:
            return True, "OK"
        else:
            error_msg = result.stderr or result.stdout or "Unknown error"
            return False, error_msg.strip()[:200]
    except subprocess.TimeoutExpired:
        return False, "Health check timeout"
    except Exception as e:
        return False, str(e)[:200]

def attempt_recovery(service_name, recovery_command):
    try:
        logger.info(f"Attempting recovery for {service_name}...")
        result = subprocess.run(recovery_command, shell=True, capture_output=True, timeout=10, text=True)
        if result.returncode == 0:
            logger.info(f"✓ Recovery successful for {service_name}")
            return True
        else:
            logger.error(f"✗ Recovery failed for {service_name}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"Recovery timeout for {service_name}")
        return False
    except Exception as e:
        logger.error(f"Recovery error for {service_name}: {str(e)}")
        return False

def send_slack_alert(service_name, alert_type, details):
    try:
        color_map = {"down": "#FF0000", "recovered": "#00CC00", "recovery_failed": "#FF6600"}
        color = color_map.get(alert_type, "#CCCCCC")
        emoji_map = {"down": "🚨", "recovered": "✅", "recovery_failed": "⚠️"}
        emoji = emoji_map.get(alert_type, "ℹ️")
        
        payload = {
            "attachments": [{
                "color": color,
                "title": f"{emoji} {service_name}: {alert_type.upper()}",
                "text": details,
                "fields": [{"title": "Time", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "short": True}]
            }]
        }
        requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Error sending Slack alert: {str(e)}")

service_status = {}

def monitor_services():
    global service_status
    for service_name, check_command in SERVICES_TO_MONITOR.items():
        is_healthy, message = check_service_health(service_name, check_command)
        
        if is_healthy:
            if service_status.get(service_name) == "down":
                logger.info(f"✓ {service_name} is now UP")
                send_slack_alert(service_name, "recovered", f"{service_name} has recovered")
            service_status[service_name] = "up"
        else:
            if service_status.get(service_name) != "down":
                logger.error(f"✗ {service_name} is DOWN: {message}")
                send_slack_alert(service_name, "down", f"Error: {message}")
                log_incident(service_name, "service_failure", message)
            
            if service_name in RECOVERY_COMMANDS:
                recovery_command = RECOVERY_COMMANDS[service_name]
                success = attempt_recovery(service_name, recovery_command)
                if success:
                    send_slack_alert(service_name, "recovered", f"Auto-recovery successful")
                    service_status[service_name] = "up"
                else:
                    send_slack_alert(service_name, "recovery_failed", f"Please investigate manually")
                    service_status[service_name] = "down"

def main():
    logger.info("Starting Incident Response Automation...")
    logger.info(f"Monitoring {len(SERVICES_TO_MONITOR)} services")
    
    init_database()
    for service_name in SERVICES_TO_MONITOR:
        service_status[service_name] = None
    
    try:
        while True:
            monitor_services()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Stopping Incident Response Automation")

if __name__ == "__main__":
    main()
