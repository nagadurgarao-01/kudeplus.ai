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

def analyze(pod, namespace, value):
    history[pod].append(value)
    if len(history[pod]) > 60:
        history[pod].pop(0)
    if len(history[pod]) < 5:
        return
    
    recent_avg = float(np.mean(history[pod][-5:]))
    overall = float(np.mean(history[pod]))
    
    baseline = max(overall, 1.0)
    if recent_avg > baseline * 3 and recent_avg > IOPS_THRESHOLD:
        publish_alert(
            pod=pod, namespace=namespace, severity='HIGH',
            reason=f'PVC write burst: {recent_avg:.0f} bytes/s (3x baseline of {baseline:.0f})',
            recommendation='Check disk I/O limits and PVC provisioner'
        )

if __name__ == '__main__':
    print('Storage Worker running...')
    try:
        info = r.xinfo_stream('metrics.storage')
        last_id = info.get('last-generated-id', '0')
    except Exception:
        last_id = '0'

    while True:
        try:
            msgs = r.xread({'metrics.storage': last_id}, count=50, block=5000)
            if msgs:
                for stream, records in msgs:
                    for rec_id, data in records:
                        try:
                            analyze(data['pod'], data.get('namespace', 'default'), float(data['value']))
                        except Exception as parse_err:
                            print(f"[Storage Worker] Error processing record {rec_id}: {parse_err}")
                        last_id = rec_id
        except Exception as e:
            print(f"[Storage Worker] Stream read error: {e}")
            time.sleep(2)
