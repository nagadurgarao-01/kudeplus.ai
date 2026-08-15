import sys
import asyncio
import sqlite3
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from correlation.graph_store import get_graph_json

app = FastAPI(title='KubePulse AI API', version='1.0.0')

# Enable CORS for frontend dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)

r = config.get_redis_client()

def get_db_connection():
    con = sqlite3.connect(config.DB_PATH, timeout=5.0)
    con.execute('PRAGMA journal_mode=WAL;')
    con.execute('PRAGMA busy_timeout=5000;')
    # Ensure tables exist
    con.execute('''CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pod TEXT, namespace TEXT, severity TEXT,
        reason TEXT, recommendation TEXT,
        nlp_summary TEXT, timestamp INTEGER
    )''')
    return con

@app.get('/api/health')
def health():
    redis_ok = False
    try:
        redis_ok = r.ping()
    except Exception:
        redis_ok = False
    return {
        "status": "healthy",
        "redis_connected": redis_ok,
        "database": config.DB_PATH
    }

@app.get('/api/incidents')
def get_incidents(limit: int = 30):
    try:
        con = get_db_connection()
        cur = con.cursor()
        rows = cur.execute(
            'SELECT pod, namespace, severity, reason, recommendation, nlp_summary, timestamp '
            'FROM incidents ORDER BY timestamp DESC LIMIT ?', (limit,)
        ).fetchall()
        con.close()
        return [
            {
                'pod': r[0],
                'namespace': r[1],
                'severity': r[2],
                'reason': r[3],
                'recommendation': r[4],
                'nlp_summary': r[5],
                'timestamp': r[6]
            }
            for r in rows
        ]
    except Exception as e:
        return {"error": str(e), "data": []}

@app.get('/api/graph')
def get_graph(): 
    try:
        return get_graph_json()
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}

@app.get('/api/debug/redis')
def debug_redis():
    try:
        correlations = r.hgetall('correlations')
        keys = list(r.scan_iter('*', count=100))
        return {
            'correlations': correlations,
            'keys': keys
        }
    except Exception as e:
        return {"error": str(e)}

@app.websocket('/ws/alerts')
async def alerts_ws(ws: WebSocket):
    await ws.accept()
    last_id = '$'
    
    # Check if there is an existing stream ID
    try:
        info = r.xinfo_stream('incidents.enriched')
        last_id = info.get('last-generated-id', '$')
    except Exception:
        last_id = '$'

    try:
        while True:
            try:
                # Read from Redis stream in a thread pool to avoid blocking asyncio event loop
                msgs = await asyncio.to_thread(
                    r.xread, {'incidents.enriched': last_id}, count=5, block=1000
                )
                if msgs:
                    for stream, records in msgs:
                        for rec_id, data in records:
                            await ws.send_json(data)
                            last_id = rec_id
            except (ConnectionError, TimeoutError):
                pass
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket] Client connection terminated: {e}")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('api.main:app', host=config.API_HOST, port=config.API_PORT, reload=True)
