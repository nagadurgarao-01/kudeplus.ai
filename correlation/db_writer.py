import redis, sqlite3, json, time

r   = redis.Redis(host='localhost', port=6379, decode_responses=True)
con = sqlite3.connect('kubepulse.db', check_same_thread=False)
cur = con.cursor()

# Create tables
cur.execute('''CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pod TEXT, namespace TEXT, metric TEXT,
    value REAL, timestamp INTEGER
    )''')
cur.execute('''CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pod TEXT, namespace TEXT, severity TEXT,
    reason TEXT, recommendation TEXT,
    nlp_summary TEXT, timestamp INTEGER
    )''')
con.commit()

last_incident_id = '0'

def persist_metrics(stream):
    try:
        records = r.xrange(stream, count=50)
        for _, data in records:
            cur.execute('INSERT INTO metrics VALUES (NULL,?,?,?,?,?)',
                        (data['pod'], data.get('namespace','default'),
                         stream, float(data['value']), int(time.time())))
        con.commit()
    except Exception as e:
        print(f"Error persisting metrics: {e}")

def persist_incidents():
    global last_incident_id
    try:
        msgs = r.xread({'incidents.enriched': last_incident_id}, count=20, block=0)
        if msgs:
            for stream, records in msgs:
                for rec_id, data in records:
                    cur.execute('INSERT INTO incidents VALUES (NULL,?,?,?,?,?,?,?)',
                                (data.get('pod',''), data.get('namespace','default'),
                                 data.get('severity',''), data.get('reason',''),
                                 data.get('recommendation',''),
                                 data.get('nlp_summary',''), int(time.time())))
                    last_incident_id = rec_id
            con.commit()
            print(f"[DB] Saved {sum(len(r) for _,r in msgs)} incidents")
    except Exception as e:
        print(f"Error persisting incidents: {e}")

print('DB Writer running...')
while True:
    for stream in ['metrics.cpu','metrics.memory','metrics.storage']:
        persist_metrics(stream)
    persist_incidents()
    time.sleep(10)

