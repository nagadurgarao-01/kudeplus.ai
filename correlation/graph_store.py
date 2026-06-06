import networkx as nx, redis, json

r = redis.Redis(host='localhost', port=6379, decode_responses=True)
G = nx.DiGraph()

def update_graph():
    pairs = r.hgetall('correlations')   # set by correlation_processor
    G.clear()
    for key, corr in pairs.items():
        try:
            p1, p2 = key.split(':')
            G.add_edge(p1, p2, weight=float(corr))
        except Exception:
            continue
    return G

def get_graph_json():
    G = update_graph()
    return {
        'nodes': [{'id': n} for n in G.nodes()],
        'edges': [{'source': u, 'target': v, 'weight': d['weight']}
                  for u, v, d in G.edges(data=True)]
    }
