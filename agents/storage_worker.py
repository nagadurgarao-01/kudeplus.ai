import redis, time, numpy as np
from collections import defaultdict
from agents.base_worker import r, publish_alert

history = defaultdict(list)
IOPS_THRESHOLD = 1000

def analyze(pod, namespace, value):
    history[pod].append(value)
    if len(history[pod]) > 60: history[pod].pop(0)
    if len(history[pod]) < 5:  return
    
    recent_avg = np.mean(history[pod][-5:])
    overall    = np.mean(history[pod])
    
    if recent_avg > overall * 3 and recent_avg > IOPS_THRESHOLD:
        publish_alert(
            pod=pod, namespace=namespace, severity='HIGH',
            reason=f'PVC write burst: {recent_avg:.0f} bytes/s (3x baseline)',
            recommendation='Check disk I/O limits and PVC provisioner'
        )

print('Storage Worker running...')
last_id = '0'
while True:
    msgs = r.xread({'metrics.storage': last_id}, count=50, block=5000)
    if msgs:
        for stream, records in msgs:
            for rec_id, data in records:
                analyze(data['pod'], data['namespace'], float(data['value']))
                last_id = rec_id
