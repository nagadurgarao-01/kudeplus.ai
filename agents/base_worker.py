import redis, json, time
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

def publish_alert(pod, namespace, severity, reason, recommendation):
    alert = {
        'pod': pod,
        'namespace': namespace,
        'severity': severity,        # LOW / MEDIUM / HIGH / CRITICAL
        'reason': reason,
        'recommendation': recommendation,
        'timestamp': int(time.time())
    }
    r.xadd('incidents', alert, maxlen=500)
    print(f'[ALERT] {severity} | {pod} | {reason}')
