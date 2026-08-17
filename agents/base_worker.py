import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

r = config.get_redis_client()

last_alert_time = {}
ALERT_COOLDOWN = 15 # seconds

def publish_alert(pod, namespace, severity, reason, recommendation):
    now = int(time.time())
    alert_type = reason.split(':')[0]
    alert_key = f"{pod}:{severity}:{alert_type}"
    if alert_key in last_alert_time and (now - last_alert_time[alert_key] < ALERT_COOLDOWN):
        return

    last_alert_time[alert_key] = now
    alert = {
        'pod': pod,
        'namespace': namespace,
        'severity': severity,        # LOW / MEDIUM / HIGH / CRITICAL
        'reason': reason,
        'recommendation': recommendation,
        'timestamp': now
    }
    try:
        r.xadd('incidents', alert, maxlen=500)
        print(f'[ALERT] {severity} | {pod} | {reason}')
    except Exception as e:
        print(f"[Worker] Error publishing alert to Redis: {e}")
