import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

r = config.get_redis_client()

def publish_alert(pod, namespace, severity, reason, recommendation):
    alert = {
        'pod': pod,
        'namespace': namespace,
        'severity': severity,        # LOW / MEDIUM / HIGH / CRITICAL
        'reason': reason,
        'recommendation': recommendation,
        'timestamp': int(time.time())
    }
    try:
        r.xadd('incidents', alert, maxlen=500)
        print(f'[ALERT] {severity} | {pod} | {reason}')
    except Exception as e:
        print(f"[Worker] Error publishing alert to Redis: {e}")
