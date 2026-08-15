import sys
import time
from pathlib import Path
from collections import defaultdict
import numpy as np

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.base_worker import r, publish_alert

history = defaultdict(list)

def analyze(pod, namespace, value):
    history[pod].append(value)
    if len(history[pod]) > 60:
        history[pod].pop(0)
    if len(history[pod]) < 10:
        return    # need at least 10 readings
        
    arr = np.array(history[pod], dtype=float)
    mean = float(arr.mean())
    std = float(arr.std())
    if std < 1e-5:
        std = 1e-5
    zscore = (value - mean) / std
    
    if zscore > 3.0:
        publish_alert(
            pod=pod, namespace=namespace,
            severity='CRITICAL' if zscore > 5 else 'HIGH',
            reason=f'CPU spike detected. z-score={zscore:.2f}, value={value:.4f}',
            recommendation='Apply resource limit: cpu: 2 or enable HPA'
        )

if __name__ == '__main__':
    print('CPU Worker running...')
    last_id = '$'  # Start from new records by default or use '0' if backlog needed
    # Check if stream exists; if so, start from current tail
    try:
        info = r.xinfo_stream('metrics.cpu')
        last_id = info.get('last-generated-id', '0')
    except Exception:
        last_id = '0'

    while True:
        try:
            msgs = r.xread({'metrics.cpu': last_id}, count=50, block=5000)
            if msgs:
                for stream, records in msgs:
                    for rec_id, data in records:
                        try:
                            analyze(data['pod'], data.get('namespace', 'default'), float(data['value']))
                        except Exception as parse_err:
                            print(f"[CPU Worker] Error processing record {rec_id}: {parse_err}")
                        last_id = rec_id
        except Exception as e:
            print(f"[CPU Worker] Stream read error: {e}")
            time.sleep(2)
