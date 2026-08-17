import sys
import time
from pathlib import Path
from collections import defaultdict
import numpy as np

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.base_worker import r, publish_alert

history = defaultdict(list)

def analyze(pod, namespace, value, timestamp=None):
    ts = float(timestamp) if timestamp is not None else time.time()
    
    # Reset history if large time gap (> 30s) or non-chronological record
    if history[pod] and (ts - history[pod][-1][0] > 30 or ts < history[pod][-1][0]):
        history[pod].clear()
        
    history[pod].append((ts, value))
    
    # Keep rolling 120s window of data
    history[pod] = [(t, v) for t, v in history[pod] if ts - t <= 120]
    if len(history[pod]) > 60:
        history[pod] = history[pod][-60:]
        
    if len(history[pod]) < 3:
        return
        
    # Baseline computed on previous points
    vals = [v for t, v in history[pod][:-1]]
    if len(vals) >= 2:
        mean = float(np.mean(vals))
        std = float(np.std(vals))
        if std < 0.05:
            std = 0.05
        zscore = (value - mean) / std
    else:
        mean = value
        zscore = 0.0
    
    if zscore > 2.5 or value >= 1.0:
        publish_alert(
            pod=pod, namespace=namespace,
            severity='CRITICAL' if (zscore > 5 or value >= 2.0) else 'HIGH',
            reason=f'CPU spike detected: {value:.2f} cores (z-score={zscore:.2f}, baseline={mean:.2f})',
            recommendation='Apply resource limit: cpu: 2 or enable HPA'
        )

if __name__ == '__main__':
    print('CPU Worker running...')
    try:
        info = r.xinfo_stream('metrics.cpu')
        last_id = info.get('last-generated-id', '0')
    except Exception:
        last_id = '0'

    import redis
    while True:
        try:
            msgs = r.xread({'metrics.cpu': last_id}, count=50, block=2000)
            if msgs:
                for stream, records in msgs:
                    for rec_id, data in records:
                        try:
                            analyze(
                                data['pod'],
                                data.get('namespace', 'default'),
                                float(data['value']),
                                timestamp=data.get('timestamp')
                            )
                        except Exception as parse_err:
                            print(f"[CPU Worker] Error processing record {rec_id}: {parse_err}")
                        last_id = rec_id
        except (redis.exceptions.TimeoutError, TimeoutError):
            pass
        except Exception as e:
            print(f"[CPU Worker] Stream read error: {e}")
            time.sleep(2)
