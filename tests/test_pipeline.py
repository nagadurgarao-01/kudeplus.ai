import pytest
import numpy as np
from scipy.stats import pearsonr
import config
from correlation.correlation_processor import find_correlated_pairs_for_metric

def test_config_defaults():
    assert config.REDIS_HOST is not None
    assert config.REDIS_PORT == 6379
    assert config.API_PORT == 8000
    assert config.DEFAULT_MEM_LIMIT > 0

def test_cpu_zscore_anomaly_detection():
    # Simulate a steady baseline followed by a large spike
    history = [0.10] * 20
    spike_val = 0.95
    
    arr = np.array(history, dtype=float)
    mean = float(arr.mean())
    std = float(arr.std())
    if std < 1e-5:
        std = 1e-5
    zscore = (spike_val - mean) / std
    
    assert zscore > 5.0  # Should trigger CRITICAL alert

def test_memory_slope_oom_calculation():
    # Simulate linearly increasing memory
    times = np.array([0, 10, 20, 30, 40, 50, 60, 70, 80, 90], dtype=float)
    values = np.array([100e6, 105e6, 110e6, 115e6, 120e6, 125e6, 130e6, 135e6, 140e6, 145e6], dtype=float)
    time_diff = times - times[0]
    
    slope = np.polyfit(time_diff, values, 1)[0] # 500 KB / sec
    mem_limit = 512 * 1024 * 1024
    remaining = mem_limit - values[-1]
    mins_to_oom = (remaining / slope) / 60
    
    assert slope > 1024
    assert mins_to_oom < 15

def test_pearson_correlation_pairs():
    # Two highly correlated pod metric series
    series_map = {
        'pod-a': [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
        'pod-b': [2.1, 4.1, 5.9, 8.2, 10.1, 11.9, 14.0, 16.1, 18.0, 20.2],
        'pod-c': [10.0, 2.0, 8.0, 1.0, 9.0, 3.0, 7.0, 2.0, 8.0, 1.0]
    }
    pairs = find_correlated_pairs_for_metric('metrics.cpu', series_map, threshold=0.85, window=10)
    assert 'pod-a:pod-b' in pairs
    assert pairs['pod-a:pod-b'] > 0.95
    assert 'pod-a:pod-c' not in pairs
