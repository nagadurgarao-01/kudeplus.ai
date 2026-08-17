import sys
import time
from pathlib import Path
from collections import defaultdict
import numpy as np

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.base_worker import r, publish_alert

history = defaultdict(list)
IOPS_THRESHOLD = 1000

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
    
    recent_vals = [v for t, v in history[pod][-3:]]
    recent_avg = float(np.mean(recent_vals))
    all_vals = [v for t, v in history[pod]]
    overall = float(np.mean(all_vals))
    
    baseline = max(overall, 1.0)
    if (recent_avg > baseline * 2.5 and recent_avg > IOPS_THRESHOLD) or value > 1000000:
        publish_alert(
            pod=pod, namespace=namespace, severity='HIGH',
            reason=f'PVC write burst: {recent_avg:.0f} bytes/s (baseline: {baseline:.0f})',
            recommendation='Check disk I/O limits and PVC provisioner'
        )

if __name__ == '__main__':
    print('Storage Worker running...')
    try:
        info = r.xinfo_stream('metrics.storage')
        last_id = info.get('last-generated-id', '0')
    except Exception:
        last_id = '0'

    import redis
    while True:
        try:
            msgs = r.xread({'metrics.storage': last_id}, count=50, block=2000)
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
                            print(f"[Storage Worker] Error processing record {rec_id}: {parse_err}")
                        last_id = rec_id
        except (redis.exceptions.TimeoutError, TimeoutError):
            pass
        except Exception as e:
            print(f"[Storage Worker] Stream read error: {e}")
            time.sleep(2)
