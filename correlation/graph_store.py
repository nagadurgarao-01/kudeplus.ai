import sys
from pathlib import Path
import networkx as nx

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

r = config.get_redis_client()
G = nx.DiGraph()

def update_graph():
    G.clear()
    
    # 1. Add all active known pods as nodes
    try:
        for pod_key in r.scan_iter(match='pod:*', count=50):
            pod_name = pod_key.replace('pod:', '')
            if pod_name:
                G.add_node(pod_name)
    except Exception as e:
        print(f"[GraphStore] Error scanning active pods: {e}")

    # 2. Add correlated edges
    try:
        pairs = r.hgetall('correlations') or {}
        for key, corr in pairs.items():
            try:
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

def get_graph_json():
    graph = update_graph()
    return {
        'nodes': [{'id': n} for n in graph.nodes()],
        'edges': [{'source': u, 'target': v, 'weight': d.get('weight', 1.0)}
                  for u, v, d in graph.edges(data=True)]
    }
