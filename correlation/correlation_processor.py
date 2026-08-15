import sys
import time
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.stats import pearsonr

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

r = config.get_redis_client()

def load_metric_series(stream, max_entries=200):
    """
    Loads recent metrics in chronological order for each pod.
    Returns: dict of pod -> list of float values (oldest to newest)
    """
    series = defaultdict(list)
    try:
        records = r.xrevrange(stream, count=max_entries)
        # xrevrange returns newest first; reverse to get chronological order
        for rec_id, data in reversed(records):
            pod = data.get('pod', 'unknown')
            if pod == 'unknown':
                continue
            try:
                val = float(data.get('value', 0.0))
                series[pod].append(val)
            except (ValueError, TypeError):
                continue
    except Exception as e:
        print(f"[Correlation] Error reading stream {stream}: {e}")
    return series

def find_correlated_pairs_for_metric(metric_name, series_map, threshold=0.85, window=20):
    """
    Computes pairwise Pearson correlation for pods with sufficient data points in the same metric.
    """
    pods = [p for p, vals in series_map.items() if len(vals) >= window]
    pairs = {}
    
    for i in range(len(pods)):
        for j in range(i + 1, len(pods)):
            p1, p2 = pods[i], pods[j]
            a = np.array(series_map[p1][-window:], dtype=float)
            b = np.array(series_map[p2][-window:], dtype=float)
            
            # Skip if constant signal (std dev near 0 produces NaN in pearsonr)
            if np.std(a) < 1e-6 or np.std(b) < 1e-6:
                continue
                
            try:
                corr, _ = pearsonr(a, b)
                if not np.isnan(corr) and abs(corr) >= threshold:
                    key = f"{p1}:{p2}"
                    pairs[key] = round(float(corr), 3)
            except Exception:
                continue
                
    return pairs

def run_correlation_cycle(threshold=0.85):
    all_correlations = {}
    streams = ['metrics.cpu', 'metrics.memory', 'metrics.storage']
    
    for stream in streams:
        series_map = load_metric_series(stream)
        pairs = find_correlated_pairs_for_metric(stream, series_map, threshold=threshold)
        for pair_key, corr in pairs.items():
            # Retain maximum absolute correlation if multiple metrics correlate
            if pair_key not in all_correlations or abs(corr) > abs(all_correlations[pair_key]):
                all_correlations[pair_key] = corr

    # Update Redis hash
    try:
        r.delete('correlations') # Clear old graph edges
        if all_correlations:
            r.hset('correlations', mapping={k: str(v) for k, v in all_correlations.items()})
    except Exception as e:
        print(f"[Correlation] Error saving correlations to Redis: {e}")

    return all_correlations

if __name__ == '__main__':
    print('Correlation Processor running (metric-separated & chronological analysis)...')
    while True:
        try:
            correlations = run_correlation_cycle()
            if correlations:
                print(f"[Correlation] Found {len(correlations)} correlated pod pairs:")
                for pair, corr in correlations.items():
                    p1, p2 = pair.split(':')
                    print(f"  🔗 {p1} <-> {p2} (r = {corr})")
        except Exception as e:
            print(f"[Correlation] Error in processing cycle: {e}")
        time.sleep(30)
