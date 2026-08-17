import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import requests
import config

r = config.get_redis_client()

QUERIES = {
    'metrics.cpu':     'rate(container_cpu_usage_seconds_total[1m])',
    'metrics.memory':  'container_memory_usage_bytes',
    'metrics.storage': 'rate(container_fs_writes_bytes_total[1m])',
}

def fetch_metric(query):
    try:
        resp = requests.get(f'{config.PROMETHEUS_URL}/api/v1/query',
                            params={'query': query}, timeout=5)
        if resp.status_code == 200:
            return resp.json().get('data', {}).get('result', [])
        print(f"[Normalizer] Prometheus returned status {resp.status_code}")
        return []
    except Exception as e:
        print(f"[Normalizer] Error fetching metric from {config.PROMETHEUS_URL}: {e}")
        return []

def normalize(metric_name, results):
    events = []
    for item in results:
        labels = item.get('metric', {})
        pod = labels.get('pod', 'unknown')
        ns  = labels.get('namespace', 'default')
        if pod == 'unknown' or ns in ['kube-system', 'monitoring']:
            continue
            
        try:
            val = float(item['value'][1])
        except (IndexError, ValueError, TypeError):
            continue

        events.append({
            'pod': pod, 
            'namespace': ns,
            'metric': metric_name,
            'value': round(val, 4),
            'timestamp': int(time.time())
        })
        
        # Register the pod in Redis so the log worker and correlation know it exists
        try:
            r.hset(f'pod:{pod}', mapping={'pod': pod, 'namespace': ns})
            r.expire(f'pod:{pod}', 60) # auto-remove if pod is offline for 60s
        except Exception as e:
            print(f"[Normalizer] Redis error updating pod key: {e}")
        
    return events

if __name__ == '__main__':
    print(f'Normalizer running. Target Prometheus: {config.PROMETHEUS_URL}. Pushing to Redis every 5s...')
    while True:
        try:
            for stream, query in QUERIES.items():
                results = fetch_metric(query)
                for event in normalize(stream, results):
                    r.xadd(stream, event, maxlen=1000)
        except Exception as loop_err:
            print(f"[Normalizer] Unexpected error in loop: {loop_err}")
        time.sleep(5)
