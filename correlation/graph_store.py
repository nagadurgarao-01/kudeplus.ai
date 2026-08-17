import sys
import sqlite3
import subprocess
from pathlib import Path
import networkx as nx

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

r = config.get_redis_client()
G = nx.DiGraph()

KNOWN_DEPENDENCIES = [
    # Core Microservice Mesh
    ('api-gateway', 'auth-service'),
    ('api-gateway', 'order-service'),
    ('api-gateway', 'inventory-service'),
    ('order-service', 'payment-service'),
    ('order-service', 'inventory-service'),
    ('payment-service', 'auth-service'),
    
    # Stress & Chaos Workload Relationships
    ('high-cpu-batch-job', 'order-service'),
    ('memory-leak-worker', 'payment-service'),
    ('cpu-chaos', 'high-cpu-batch-job'),
    ('cpu-stress', 'high-cpu-batch-job'),
    ('mem-chaos', 'payment-service'),
    ('disk-chaos', 'order-service'),
]

def update_graph():
    G.clear()
    nodes = set()
    
    # 1. Discover pods from active Kubernetes cluster
    try:
        out = subprocess.check_output(
            ["kubectl", "get", "pods", "-n", "default", "-o", "jsonpath={.items[*].metadata.name}"],
            timeout=2
        ).decode('utf-8')
        for p in out.strip().split():
            if p:
                nodes.add(p)
    except Exception:
        pass

    # 2. Discover pods from Redis streams
    for stream in ['metrics.cpu', 'metrics.memory', 'metrics.storage', 'incidents', 'incidents.enriched']:
        try:
            records = r.xrevrange(stream, count=60)
            for rec_id, d in records:
                pod = d.get('pod')
                if pod and pod != 'unknown':
                    nodes.add(pod)
        except Exception:
            pass

    # 3. Discover pods from SQLite history
    try:
        con = sqlite3.connect(config.DB_PATH, timeout=2.0)
        for row in con.execute('SELECT DISTINCT pod FROM metrics WHERE pod != "unknown"').fetchall():
            nodes.add(row[0])
        for row in con.execute('SELECT DISTINCT pod FROM incidents WHERE pod != ""').fetchall():
            nodes.add(row[0])
        con.close()
    except Exception:
        pass

    # 4. Discover pods from Redis pod:* keys
    try:
        for pod_key in r.scan_iter(match='pod:*', count=50):
            pod_name = pod_key.replace('pod:', '')
            if pod_name:
                nodes.add(pod_name)
    except Exception:
        pass

    # Add all discovered nodes to graph
    for n in nodes:
        G.add_node(n)

    # 5. Add structural microservice & chaos dependencies
    for src_prefix, tgt_prefix in KNOWN_DEPENDENCIES:
        src_matches = [n for n in nodes if n.startswith(src_prefix)]
        tgt_matches = [n for n in nodes if n.startswith(tgt_prefix)]
        for s in src_matches:
            for t in tgt_matches:
                if s != t:
                    G.add_edge(s, t, weight=0.88)

    # 6. Add statistical Pearson correlation links from correlation processor
    try:
        pairs = r.hgetall('correlations') or {}
        for key, corr in pairs.items():
            try:
                if ':' in key:
                    p1, p2 = key.split(':')
                    weight = float(corr)
                    G.add_node(p1)
                    G.add_node(p2)
                    G.add_edge(p1, p2, weight=weight)
            except Exception:
                continue
    except Exception as e:
        print(f"[GraphStore] Error reading correlations: {e}")

    return G

def get_pod_meta(pod_name):
    if 'api-gateway' in pod_name:
        return 'API Gateway', 'Ingress Gateway', '🌐'
    elif 'auth' in pod_name:
        return 'Auth Service', 'Security & Auth', '🔐'
    elif 'order' in pod_name:
        return 'Order Service', 'Core Backend', '📦'
    elif 'payment' in pod_name:
        return 'Payment Service', 'Payment Gateway', '💳'
    elif 'inventory' in pod_name:
        return 'Inventory Service', 'Catalog DB', '🗄️'
    elif 'high-cpu' in pod_name:
        return 'CPU Batch Job', 'Analytics Worker', '⚡'
    elif 'memory-leak' in pod_name:
        return 'Memory Worker', 'Load Tester', '📈'
    elif 'cpu-chaos' in pod_name or 'cpu-stress' in pod_name:
        return 'CPU Stressor', 'Chaos Engine', '🔥'
    elif 'mem-chaos' in pod_name:
        return 'Memory Stressor', 'Chaos Engine', '💥'
    elif 'disk-chaos' in pod_name:
        return 'Disk Stressor', 'Chaos Engine', '💾'
    return pod_name.split('-')[0].capitalize(), 'Workload', '⚙️'

def get_graph_json():
    graph = update_graph()
    
    # Pre-fetch recent incidents and metrics for node enrichment
    incidents_map = {}
    try:
        for rec_id, d in r.xrevrange('incidents', count=50):
            p = d.get('pod')
            if p and p not in incidents_map:
                incidents_map[p] = d
    except Exception:
        pass

    cpu_map = {}
    try:
        for rec_id, d in r.xrevrange('metrics.cpu', count=80):
            p = d.get('pod')
            if p and p not in cpu_map:
                try:
                    cpu_map[p] = round(float(d.get('value', 0)), 3)
                except Exception:
                    pass
    except Exception:
        pass

    mem_map = {}
    try:
        for rec_id, d in r.xrevrange('metrics.memory', count=80):
            p = d.get('pod')
            if p and p not in mem_map:
                try:
                    mem_map[p] = round(float(d.get('value', 0)) / (1024 * 1024), 1)
                except Exception:
                    pass
    except Exception:
        pass

    enriched_nodes = []
    for n in graph.nodes():
        role, category, icon = get_pod_meta(n)
        inc = incidents_map.get(n)
        severity = inc.get('severity', 'HEALTHY') if inc else 'HEALTHY'
        
        enriched_nodes.append({
            'id': n,
            'name': role,
            'pod': n,
            'role': role,
            'category': category,
            'icon': icon,
            'severity': severity,
            'status': 'Critical' if severity == 'CRITICAL' else ('Degraded' if severity == 'HIGH' else 'Healthy'),
            'cpu': cpu_map.get(n),
            'memory_mb': mem_map.get(n),
            'reason': inc.get('reason') if inc else None,
            'recommendation': inc.get('recommendation') if inc else None,
        })

    return {
        'nodes': enriched_nodes,
        'edges': [{'source': u, 'target': v, 'weight': d.get('weight', 1.0)}
                  for u, v, d in graph.edges(data=True)]
    }


