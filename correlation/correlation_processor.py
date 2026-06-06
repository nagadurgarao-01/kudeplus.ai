import redis, json, time, numpy as np
from scipy.stats import pearsonr
from collections import defaultdict

r = redis.Redis(host='localhost', port=6379, decode_responses=True)
pod_series = defaultdict(list)   # pod -> list of metric values

def load_recent_metrics(stream, max_entries=200):
    records = r.xrevrange(stream, count=max_entries)
    for rec_id, data in records:
        pod = data.get('pod', 'unknown')
        val = float(data.get('value', 0))
        pod_series[pod].append(val)

def find_correlated_pairs(threshold=0.85):
    pods = [p for p, vals in pod_series.items() if len(vals) >= 20]
    pairs = []
    for i in range(len(pods)):
        for j in range(i+1, len(pods)):
            a = pod_series[pods[i]][-20:]
            b = pod_series[pods[j]][-20:]
            if len(a) == len(b):
                corr, _ = pearsonr(a, b)
                if abs(corr) > threshold:
                    pairs.append((pods[i], pods[j], round(corr, 3)))
                    r.hset('correlations', f'{pods[i]}:{pods[j]}', corr)
    return pairs

print('Correlation Processor running...')
while True:
    pod_series.clear()
    for stream in ['metrics.cpu', 'metrics.memory', 'metrics.storage']:
        load_recent_metrics(stream)
    pairs = find_correlated_pairs()
    for p1, p2, corr in pairs:
        print(f'  Correlated: {p1} <-> {p2}  r={corr}')
    time.sleep(30)
