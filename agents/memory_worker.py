import redis, time, numpy as np
from collections import defaultdict
from agents.base_worker import r, publish_alert

history  = defaultdict(list)
MEM_LIMIT = 512 * 1024 * 1024   # 512 MB default limit

def analyze(pod, namespace, value):
    history[pod].append((time.time(), value))
    if len(history[pod]) > 60: history[pod].pop(0)
    if len(history[pod]) < 10: return
    
    times  = np.array([t for t, v in history[pod]])
    values = np.array([v for t, v in history[pod]])
    slope  = np.polyfit(times - times[0], values, 1)[0]   # bytes/sec
    
    if slope > 0:
        remaining = MEM_LIMIT - values[-1]
        mins_to_oom = (remaining / slope) / 60 if slope > 0 else 9999
        if mins_to_oom < 15:
            publish_alert(
                pod=pod, namespace=namespace, severity='CRITICAL',
                reason=f'Memory leak: OOM forecast in {mins_to_oom:.1f} min',
                recommendation='Restart pod or increase memory limit'
            )

print('Memory Worker running...')
last_id = '0'
while True:
    msgs = r.xread({'metrics.memory': last_id}, count=50, block=5000)
    if msgs:
        for stream, records in msgs:
            for rec_id, data in records:
                analyze(data['pod'], data['namespace'], float(data['value']))
                last_id = rec_id
