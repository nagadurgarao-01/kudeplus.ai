import redis, requests, json, time

PROMETHEUS = 'http://localhost:9090'
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

QUERIES = {
    'metrics.cpu':     'rate(container_cpu_usage_seconds_total[1m])',
    'metrics.memory':  'container_memory_usage_bytes',
    'metrics.storage': 'container_fs_writes_bytes_total',
}

def fetch_metric(query):
    try:
        resp = requests.get(f'{PROMETHEUS}/api/v1/query',
                            params={'query': query}, timeout=5)
        return resp.json().get('data', {}).get('result', [])
    except Exception as e:
        print(f"Error fetching metric: {e}")
        return []

def normalize(metric_name, results):
    events = []
    for item in results:
        labels = item['metric']
        pod = labels.get('pod', 'unknown')
        ns  = labels.get('namespace', 'default')
        if pod == 'unknown' or ns in ['kube-system', 'monitoring']:
            continue
            
        val = float(item['value'][1])
        events.append({
            'pod': pod, 
            'namespace': ns,
            'metric': metric_name,
            'value': round(val, 4),
            'timestamp': int(time.time())
        })
        
        # --- BUG FIX FOR LOG WORKER ---
        # Register the pod in Redis so the log worker knows it exists
        r.hset(f'pod:{pod}', mapping={'pod': pod, 'namespace': ns})
        r.expire(f'pod:{pod}', 60) # auto-remove if pod is offline for 60s
        
    return events

print('Normalizer running (with bug fix). Pushing to Redis every 5s...')
while True:
    for stream, query in QUERIES.items():
        results = fetch_metric(query)
        for event in normalize(stream, results):
            r.xadd(stream, event, maxlen=1000)
    time.sleep(5)
