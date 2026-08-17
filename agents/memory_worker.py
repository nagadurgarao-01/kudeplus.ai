import sys
import time
from pathlib import Path
from collections import defaultdict
import numpy as np

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from agents.base_worker import r, publish_alert

history = defaultdict(list)
MEM_LIMIT = config.DEFAULT_MEM_LIMIT

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
    
    times = np.array([t for t, v in history[pod]], dtype=float)
    values = np.array([v for t, v in history[pod]], dtype=float)
    time_diff = times - times[0]
    
    # Avoid singular matrix if all timestamps are identical or time diff too small
    if np.all(time_diff == 0) or time_diff[-1] < 1.0:
        return

    slope = np.polyfit(time_diff, values, 1)[0]   # bytes/sec
    
    if slope > 1024: # Consistently increasing memory (> 1 KB/sec)
        remaining = max(0, MEM_LIMIT - values[-1])
        mins_to_oom = (remaining / slope) / 60
        if mins_to_oom < 15:
            publish_alert(
                pod=pod, namespace=namespace, severity='CRITICAL',
                reason=f'Memory leak: OOM forecast in {mins_to_oom:.1f} min (growth rate: {slope / 1024:.1f} KB/s)',
                recommendation='Restart pod or increase memory limit'
            )
    elif values[-1] >= 0.85 * MEM_LIMIT:
        publish_alert(
            pod=pod, namespace=namespace, severity='HIGH',
            reason=f'High memory usage: {values[-1]/(1024*1024):.1f} MB ({values[-1]/MEM_LIMIT*100:.1f}% of limit)',
            recommendation='Increase pod memory limit or scale replicas'
        )

if __name__ == '__main__':
    print(f'Memory Worker running (default limit: {MEM_LIMIT / (1024*1024):.0f} MB)...')
    try:
        info = r.xinfo_stream('metrics.memory')
        last_id = info.get('last-generated-id', '0')
    except Exception:
        last_id = '0'

    import redis
    while True:
        try:
            msgs = r.xread({'metrics.memory': last_id}, count=50, block=2000)
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
                            print(f"[Memory Worker] Error processing record {rec_id}: {parse_err}")
                        last_id = rec_id
        except (redis.exceptions.TimeoutError, TimeoutError):
            pass
        except Exception as e:
            print(f"[Memory Worker] Stream read error: {e}")
            time.sleep(2)
