from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import redis, json, asyncio, sqlite3
from correlation.graph_store import get_graph_json

app = FastAPI(title='KubePulse AI')

# Enable CORS so your React dashboard can connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)

r   = redis.Redis(host='localhost', port=6379, decode_responses=True)

@app.get('/api/incidents')
def get_incidents(limit: int = 20):
    try:
        con = sqlite3.connect('kubepulse.db')
        cur = con.cursor()
        rows = cur.execute(
            'SELECT pod,namespace,severity,reason,nlp_summary,timestamp'
            ' FROM incidents ORDER BY timestamp DESC LIMIT ?', (limit,)
        ).fetchall()
        con.close()
        return [{'pod':r[0],'namespace':r[1],'severity':r[2],
                 'reason':r[3],'nlp_summary':r[4],'timestamp':r[5]}
                for r in rows]
    except Exception as e:
        return {"error": str(e)}

@app.get('/api/graph')
def get_graph(): 
    return get_graph_json()

@app.get('/api/debug/redis')
def debug_redis():
    try:
        return {
            'correlations': r.hgetall('correlations'),
            'keys': r.keys('*')
        }
    except Exception as e:
        return {"error": str(e)}

@app.websocket('/ws/alerts')
async def alerts_ws(ws: WebSocket):
    await ws.accept()
    last_id = '$'
    while True:
        try:
            msgs = r.xread({'incidents.enriched': last_id}, count=5, block=1000)
            if msgs:
                for stream, records in msgs:
                    for rec_id, data in records:
                        await ws.send_json(data)
                        last_id = rec_id
        except Exception as e:
            print(f"WebSocket error: {e}")
            break
        await asyncio.sleep(0.1)
