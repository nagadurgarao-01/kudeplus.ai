import redis, json, time, numpy as np
from collections import defaultdict
from agents.base_worker import r, publish_alert

history = defaultdict(list)

def analyze(pod, namespace, value):
    history[pod].append(value)
    if len(history[pod]) > 60:
        history[pod].pop(0)
    if len(history[pod]) < 10:
        return    # need at least 10 readings
        
    arr    = np.array(history[pod])
    mean   = arr.mean()
    std    = arr.std() or 0.0001
    zscore = (value - mean) / std
    
    if zscore > 3.0:
        publish_alert(
            pod=pod, namespace=namespace,
            severity='CRITICAL' if zscore > 5 else 'HIGH',
            reason=f'CPU spike detected. z-score={zscore:.2f}, value={value:.4f}',
            recommendation='Apply resource limit: cpu: 2 or enable HPA'
        )

print('CPU Worker running...')
last_id = '0'
while True:
    msgs = r.xread({'metrics.cpu': last_id}, count=50, block=5000)
    if msgs:
        for stream, records in msgs:
            for rec_id, data in records:
                analyze(data['pod'], data['namespace'], float(data['value']))
                last_id = rec_id
