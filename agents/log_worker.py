import redis, time, requests
from collections import defaultdict
from agents.base_worker import r, publish_alert

LOKI_URL = 'http://localhost:3100'
error_buckets = defaultdict(list)

def fetch_error_count(pod):
    try:
        query = f'{{pod=~"{pod}"}} |= "error"'
        resp  = requests.get(f'{LOKI_URL}/loki/api/v1/query',
                             params={'query': query}, timeout=5)
        return len(resp.json().get('data', {}).get('result', []))
    except Exception:
        return 0

def analyze(pod, namespace):
    count = fetch_error_count(pod)
    error_buckets[pod].append(count)
    if len(error_buckets[pod]) > 10: error_buckets[pod].pop(0)
    if len(error_buckets[pod]) < 3:  return
    
    baseline = sum(error_buckets[pod][:-1]) / len(error_buckets[pod][:-1]) or 1
    if count > baseline * 5:
        publish_alert(
            pod=pod, namespace=namespace, severity='HIGH',
            reason=f'Error burst: {count} errors vs {baseline:.0f} baseline',
            recommendation='Check pod logs: kubectl logs ' + pod
        )

print('Log Worker running...')
while True:
    pods = r.keys('pod:*')
    for pod_key in pods:
        pod_data = r.hgetall(pod_key)
        if pod_data:
            analyze(pod_data.get('pod',''), pod_data.get('namespace','default'))
    time.sleep(30)
