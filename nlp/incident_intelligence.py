import redis, json, requests, time

r = redis.Redis(host='localhost', port=6379, decode_responses=True)
OLLAMA = 'http://192.168.56.1:11434/api/generate'
last_id = '0'

def build_prompt(alert):
    return f'''You are a Kubernetes operations AI.
An alert was triggered. Write a 2-sentence incident summary
with one concrete recommendation.
Pod: {alert['pod']}
Namespace: {alert['namespace']}
Severity: {alert['severity']}
Reason: {alert['reason']}
Respond in plain English. No bullet points.'''

def get_nlp_summary(alert):
    try:
        resp = requests.post(OLLAMA, json={
            'model': 'phi3:mini', # Optimized for your RAM
            'prompt': build_prompt(alert),
            'stream': False
        }, timeout=30)
        return resp.json().get('response', '').strip()
    except Exception as e:
        print(f"Ollama API Error: {e}")
        return "AI analysis unavailable (check if Ollama is running)."

print('Incident Intelligence running...')
while True:
    msgs = r.xread({'incidents': last_id}, count=5, block=10000)
    if msgs:
        for stream, records in msgs:
            for rec_id, alert in records:
                summary = get_nlp_summary(alert)
                alert['nlp_summary'] = summary
                r.xadd('incidents.enriched', alert, maxlen=200)
                print(f'[NLP] {summary}')
                last_id = rec_id
