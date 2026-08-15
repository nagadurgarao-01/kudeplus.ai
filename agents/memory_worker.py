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

def analyze(pod, namespace, value):
    now = time.time()
    history[pod].append((now, value))
    if len(history[pod]) > 60:
        history[pod].pop(0)
    if len(history[pod]) < 10:
        return
    
    times = np.array([t for t, v in history[pod]], dtype=float)
    values = np.array([v for t, v in history[pod]], dtype=float)
    time_diff = times - times[0]
    
    # Avoid singular matrix if all timestamps are identical
    if np.all(time_diff == 0):
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

if __name__ == '__main__':
    print(f'Memory Worker running (default limit: {MEM_LIMIT / (1024*1024):.0f} MB)...')
    try:
        info = r.xinfo_stream('metrics.memory')
        last_id = info.get('last-generated-id', '0')
    except Exception:
        last_id = '0'

    while True:
        try:
            msgs = r.xread({'metrics.memory': last_id}, count=50, block=5000)
            if msgs:
                for stream, records in msgs:
                    for rec_id, data in records:
                        try:
                            analyze(data['pod'], data.get('namespace', 'default'), float(data['value']))
                        except Exception as parse_err:
                            print(f"[Memory Worker] Error processing record {rec_id}: {parse_err}")
                        last_id = rec_id
        except Exception as e:
            print(f"[Memory Worker] Stream read error: {e}")
            time.sleep(2)
