#!/usr/bin/env python3
"""
KubePulse AI - Artificial Critical Incident Generator
Simulates realistic CRITICAL failure scenarios across multiple microservices:
1. Critical OOM Memory Exhaustion (forecast < 2 minutes)
2. Extreme CPU Saturation Spike (4+ cores, Z-score > 6.0)
3. Cascaded Storage PVC I/O Bottleneck
4. Critical Application Fatal Error Burst (500 internal server errors)
"""

import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from agents.base_worker import publish_alert

def inject_artificial_criticals():
    r = config.get_redis_client()
    now = int(time.time())

    print("=====================================================")
    print("   🚨 Injecting Artificial CRITICAL Incidents 🚨     ")
    print("=====================================================")

    critical_scenarios = [
        {
            "pod": "payment-service-85dff46ddc-m7877",
            "namespace": "default",
            "severity": "CRITICAL",
            "reason": "Memory leak: OOM forecast in 1.4 min (growth rate: 18450.2 KB/s, current: 485.2 MB / 512 MB)",
            "recommendation": "Emergency restart payment pod, scale replicas to 3, and increase memory limit to 1Gi.",
        },
        {
            "pod": "high-cpu-batch-job-78bf5558dd-qqgcg",
            "namespace": "default",
            "severity": "CRITICAL",
            "reason": "CPU saturation spike: 3.85 cores (z-score=6.42, baseline=0.25 cores)",
            "recommendation": "Throttle background analytics worker queue and enable Kubernetes HPA auto-scaling.",
        },
        {
            "pod": "order-service-55c96f7bc5-7vrz5",
            "namespace": "default",
            "severity": "CRITICAL",
            "reason": "PVC I/O saturation: 42.5 MB/s write burst (15x baseline of 2.8 MB/s), IOPS queue depth critical",
            "recommendation": "Verify database persistent volume provisioner and check for unindexed batch write loops.",
        },
        {
            "pod": "auth-service-5bb86ccc57-987n4",
            "namespace": "default",
            "severity": "CRITICAL",
            "reason": "Fatal error storm: 284 errors/min detected (12x baseline), connection pool exhaustion to identity DB",
            "recommendation": "Restart auth service connection pool and verify identity database replica availability.",
        },
    ]

    for idx, alert in enumerate(critical_scenarios, 1):
        print(f"\n[{idx}/4] Publishing CRITICAL Incident for {alert['pod']}...")
        alert['timestamp'] = now
        
        # Publish directly to incidents bus
        try:
            r.xadd('incidents', alert, maxlen=500)
            print(f"  ✅ Published to 'incidents' stream: {alert['reason']}")
        except Exception as e:
            print(f"  ❌ Error publishing incident: {e}")
            
        time.sleep(1)

    print("\n=====================================================")
    print("🎯 Artificial Criticals Injected Successfully!")
    print("🔍 Verify NLP Enrichment: python3 -c \"import config; r=config.get_redis_client(); print(r.xrevrange('incidents.enriched', count=4))\"")
    print("🌐 View in Dashboard: http://localhost:3001")
    print("📡 View in API: curl http://localhost:8000/api/incidents")
    print("=====================================================")

if __name__ == '__main__':
    inject_artificial_criticals()
