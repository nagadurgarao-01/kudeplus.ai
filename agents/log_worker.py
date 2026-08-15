import sys
import time
from pathlib import Path
from collections import defaultdict
import requests

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from agents.base_worker import r, publish_alert

error_buckets = defaultdict(list)

def fetch_error_count(pod):
    try:
        query = f'{{pod=~"{pod}"}} |= "error"'
        resp = requests.get(f'{config.LOKI_URL}/loki/api/v1/query',
                            params={'query': query}, timeout=5)
        if resp.status_code == 200:
            return len(resp.json().get('data', {}).get('result', []))
        return 0
    except Exception as e:
        return 0

def analyze(pod, namespace):
    count = fetch_error_count(pod)
    error_buckets[pod].append(count)
    if len(error_buckets[pod]) > 10:
        error_buckets[pod].pop(0)
    if len(error_buckets[pod]) < 3:
        return
    
    prev_counts = error_buckets[pod][:-1]
    baseline = sum(prev_counts) / len(prev_counts) if prev_counts else 1.0
    baseline = max(baseline, 1.0)
    
    if count > baseline * 5:
        publish_alert(
            pod=pod, namespace=namespace, severity='HIGH',
            reason=f'Error burst: {count} errors vs {baseline:.0f} baseline',
            recommendation=f'Check pod logs: kubectl logs {pod} -n {namespace}'
        )

if __name__ == '__main__':
    print(f'Log Worker running. Target Loki: {config.LOKI_URL}...')
    while True:
        try:
            # Use scan_iter instead of blocking r.keys()
            for pod_key in r.scan_iter(match='pod:*', count=50):
                try:
                    pod_data = r.hgetall(pod_key)
                    if pod_data and 'pod' in pod_data:
                        analyze(pod_data.get('pod', ''), pod_data.get('namespace', 'default'))
                except Exception as pod_err:
                    print(f"[Log Worker] Error checking pod key {pod_key}: {pod_err}")
        except Exception as e:
            print(f"[Log Worker] Iteration error: {e}")
        time.sleep(30)
