#!/usr/bin/env python3
"""
KubePulse AI - Advanced Multi-Vector Artificial Chaos Simulator
Generates high-fidelity telemetry chaos streams and multi-signal stress events.
"""

import sys
import time
import random
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

r = config.get_redis_client()

def print_banner(title):
    print("\n" + "=" * 60)
    print(f"   ⚡ {title} ⚡")
    print("=" * 60)

def simulate_memory_leak_stream(pod_name="payment-service-85dff46ddc-m7877", base_mb=120, growth_rate_mb_s=15, duration_ticks=8):
    """
    Feeds a series of rapidly increasing memory telemetry points into metrics.memory.
    Forces memory_worker.py to compute slope > 1024 bytes/s and forecast OOM < 15 min.
    """
    print_banner(f"Simulating Rapid Memory Leak on {pod_name}")
    start_time = int(time.time()) - (duration_ticks * 5)
    
    current_bytes = base_mb * 1024 * 1024
    growth_bytes = growth_rate_mb_s * 1024 * 1024
    
    for i in range(duration_ticks):
        ts = start_time + (i * 5)
        current_bytes += growth_bytes + random.randint(-50000, 50000)
        
        event = {
            'pod': pod_name,
            'namespace': 'default',
            'metric': 'metrics.memory',
            'value': round(float(current_bytes), 2),
            'timestamp': ts
        }
        r.xadd('metrics.memory', event, maxlen=1000)
        print(f"  📈 [metrics.memory] {pod_name} -> {current_bytes/(1024*1024):.1f} MB (ts={ts})")
        time.sleep(0.4)

def simulate_cpu_spike_stream(pod_name="high-cpu-batch-job-78bf5558dd-qqgcg", duration_ticks=8):
    """
    Feeds a low baseline followed by a massive CPU surge into metrics.cpu.
    Forces cpu_worker.py to compute Z-score > 4.0 and trigger CPU spike incident.
    """
    print_banner(f"Simulating CPU Saturation Spike on {pod_name}")
    start_time = int(time.time()) - (duration_ticks * 5)
    
    # First 4 ticks: low baseline (0.15 - 0.25 cores)
    for i in range(4):
        ts = start_time + (i * 5)
        val = round(random.uniform(0.12, 0.22), 4)
        event = {'pod': pod_name, 'namespace': 'default', 'metric': 'metrics.cpu', 'value': val, 'timestamp': ts}
        r.xadd('metrics.cpu', event, maxlen=1000)
        print(f"  📊 [metrics.cpu] {pod_name} -> Baseline {val:.2f} cores (ts={ts})")
        time.sleep(0.3)
        
    # Next 4 ticks: extreme spike (3.2 - 3.9 cores)
    for i in range(4, duration_ticks):
        ts = start_time + (i * 5)
        val = round(random.uniform(3.20, 3.85), 4)
        event = {'pod': pod_name, 'namespace': 'default', 'metric': 'metrics.cpu', 'value': val, 'timestamp': ts}
        r.xadd('metrics.cpu', event, maxlen=1000)
        print(f"  🔥 [metrics.cpu] {pod_name} -> SPIKE {val:.2f} cores! (ts={ts})")
        time.sleep(0.3)

def simulate_storage_burst_stream(pod_name="order-service-55c96f7bc5-7vrz5", duration_ticks=6):
    """
    Feeds an I/O write burst into metrics.storage.
    Forces storage_worker.py to detect PVC write throughput saturation.
    """
    print_banner(f"Simulating PVC I/O Burst on {pod_name}")
    start_time = int(time.time()) - (duration_ticks * 5)
    
    for i in range(duration_ticks):
        ts = start_time + (i * 5)
        # Write burst rate in bytes/sec (40 - 55 MB/s)
        rate = round(random.uniform(40 * 1024 * 1024, 55 * 1024 * 1024), 2)
        event = {'pod': pod_name, 'namespace': 'default', 'metric': 'metrics.storage', 'value': rate, 'timestamp': ts}
        r.xadd('metrics.storage', event, maxlen=1000)
        print(f"  💾 [metrics.storage] {pod_name} -> {rate/(1024*1024):.1f} MB/s (ts={ts})")
        time.sleep(0.3)

def simulate_cascading_chaos_storm():
    print_banner("LAUNCHING CASCADING MULTI-SIGNAL CHAOS STORM")
    print("Simulating interconnected outage across 4 critical microservices...")
    
    simulate_cpu_spike_stream("high-cpu-batch-job-78bf5558dd-qqgcg", duration_ticks=6)
    time.sleep(1)
    simulate_memory_leak_stream("payment-service-85dff46ddc-m7877", base_mb=180, growth_rate_mb_s=25, duration_ticks=6)
    time.sleep(1)
    simulate_storage_burst_stream("order-service-55c96f7bc5-7vrz5", duration_ticks=6)
    
    # Direct incident injection for auth-service DB lockup
    now = int(time.time())
    auth_alert = {
        'pod': 'auth-service-5bb86ccc57-987n4',
        'namespace': 'default',
        'severity': 'CRITICAL',
        'reason': 'Auth DB deadlocks: 310 HTTP 503s/min after upstream payment gateway timeout',
        'recommendation': 'Flush deadlock transactions, restart auth replicas, and enable circuit breaker.',
        'timestamp': now
    }
    r.xadd('incidents', auth_alert, maxlen=500)
    print(f"\n  💥 [Direct Incident] Published auth-service cascade lockup alert")

    print_banner("CHAOS STORM DEPLOYMENT COMPLETE")
    print("✅ All telemetry streams and chaos vectors injected!")
    print("🌐 Real-Time Dashboard: http://localhost:3001")
    print("📡 Query API Incidents: curl http://localhost:8000/api/incidents")
    print("🗺️ Query Cluster Graph: curl http://localhost:8000/api/graph")
    print("=" * 60 + "\n")

if __name__ == '__main__':
    simulate_cascading_chaos_storm()
