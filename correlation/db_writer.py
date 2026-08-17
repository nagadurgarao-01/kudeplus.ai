import sys
import time
import sqlite3
import redis
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

r = config.get_redis_client()

def get_db_connection():
    con = sqlite3.connect(config.DB_PATH, timeout=10.0, check_same_thread=False)
    con.execute('PRAGMA journal_mode=WAL;')
    con.execute('PRAGMA synchronous=NORMAL;')
    con.execute('PRAGMA busy_timeout=5000;')
    return con

con = get_db_connection()
cur = con.cursor()

# Initialize tables & indexes
cur.execute('''CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pod TEXT, 
    namespace TEXT, 
    metric TEXT,
    value REAL, 
    timestamp INTEGER
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pod TEXT, 
    namespace TEXT, 
    severity TEXT,
    reason TEXT, 
    recommendation TEXT,
    nlp_summary TEXT, 
    timestamp INTEGER
)''')

cur.execute('CREATE INDEX IF NOT EXISTS idx_metrics_lookup ON metrics(pod, metric, timestamp DESC)')
cur.execute('CREATE INDEX IF NOT EXISTS idx_incidents_timestamp ON incidents(timestamp DESC)')
con.commit()

# Track offsets per stream to avoid duplicate insertions
last_metric_ids = {
    'metrics.cpu': '0',
    'metrics.memory': '0',
    'metrics.storage': '0'
}
last_incident_id = '0'

def persist_metrics():
    global last_metric_ids
    inserted = 0
    try:
        msgs = r.xread(last_metric_ids, count=50, block=1000)
        if msgs:
            for stream_name, records in msgs:
                for rec_id, data in records:
                    try:
                        pod = data.get('pod', 'unknown')
                        ns = data.get('namespace', 'default')
                        val = float(data.get('value', 0.0))
                        ts = int(data.get('timestamp', time.time()))
                        cur.execute(
                            'INSERT INTO metrics (pod, namespace, metric, value, timestamp) VALUES (?,?,?,?,?)',
                            (pod, ns, stream_name, val, ts)
                        )
                        last_metric_ids[stream_name] = rec_id
                        inserted += 1
                    except Exception as row_err:
                        print(f"[DB Writer] Error inserting metric row {rec_id}: {row_err}")
            if inserted > 0:
                con.commit()
    except (redis.exceptions.TimeoutError, TimeoutError):
        pass
    except Exception as e:
        print(f"[DB Writer] Error persisting metrics: {e}")

def persist_incidents():
    global last_incident_id
    try:
        msgs = r.xread({'incidents.enriched': last_incident_id}, count=20, block=1000)
        if msgs:
            count = 0
            for stream, records in msgs:
                for rec_id, data in records:
                    try:
                        cur.execute(
                            'INSERT INTO incidents (pod, namespace, severity, reason, recommendation, nlp_summary, timestamp) VALUES (?,?,?,?,?,?,?)',
                            (
                                data.get('pod', ''),
                                data.get('namespace', 'default'),
                                data.get('severity', ''),
                                data.get('reason', ''),
                                data.get('recommendation', ''),
                                data.get('nlp_summary', ''),
                                int(data.get('timestamp', time.time()))
                            )
                        )
                        last_incident_id = rec_id
                        count += 1
                    except Exception as inc_err:
                        print(f"[DB Writer] Error inserting incident {rec_id}: {inc_err}")
            if count > 0:
                con.commit()
                print(f"[DB Writer] Successfully saved {count} enriched incident(s) to SQLite")
    except (redis.exceptions.TimeoutError, TimeoutError):
        pass
    except Exception as e:
        print(f"[DB Writer] Error persisting incidents: {e}")

if __name__ == '__main__':
    print(f'DB Writer running. Target Database: {config.DB_PATH}...')
    while True:
        try:
            persist_metrics()
            persist_incidents()
        except Exception as loop_err:
            print(f"[DB Writer] Unhandled exception in loop: {loop_err}")
        time.sleep(5)
