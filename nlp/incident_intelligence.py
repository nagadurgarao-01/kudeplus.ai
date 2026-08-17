import sys
import time
import requests
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

r = config.get_redis_client()

def build_prompt(alert):
    return f"""You are a Kubernetes site reliability engineering AI assistant.
An anomaly alert was triggered in the cluster. Write a concise 2-sentence incident summary and 1 concrete mitigation action.
Pod: {alert.get('pod', 'unknown')}
Namespace: {alert.get('namespace', 'default')}
Severity: {alert.get('severity', 'UNKNOWN')}
Reason: {alert.get('reason', 'Unknown reason')}
Recommendation: {alert.get('recommendation', 'N/A')}

Respond in plain English. Do not use markdown headers or bullet points."""

def get_nlp_summary(alert):
    try:
        resp = requests.post(
            config.OLLAMA_URL,
            json={
                'model': config.OLLAMA_MODEL,
                'prompt': build_prompt(alert),
                'stream': False
            },
            timeout=15
        )
        if resp.status_code == 200:
            summary = resp.json().get('response', '').strip()
            if summary:
                return summary
        return f"AI summary unavailable (Ollama HTTP {resp.status_code}). Automated suggestion: {alert.get('recommendation', 'Check pod health')}."
    except requests.exceptions.Timeout:
        return f"AI analysis timed out. Recommendation: {alert.get('recommendation', 'Inspect pod logs')}."
    except requests.exceptions.ConnectionError:
        return f"Local LLM service offline at {config.OLLAMA_URL}. Suggested action: {alert.get('recommendation', 'Check pod')}."
    except Exception as e:
        return f"AI analysis error ({type(e).__name__}). Recommendation: {alert.get('recommendation', 'Check cluster')}."

if __name__ == '__main__':
    print(f'Incident Intelligence running. Target LLM: {config.OLLAMA_MODEL} at {config.OLLAMA_URL}...')
    try:
        info = r.xinfo_stream('incidents')
        last_id = info.get('last-generated-id', '0')
    except Exception:
        last_id = '0'

    import redis
    while True:
        try:
            msgs = r.xread({'incidents': last_id}, count=5, block=2000)
            if msgs:
                for stream, records in msgs:
                    for rec_id, alert in records:
                        try:
                            summary = get_nlp_summary(alert)
                            alert['nlp_summary'] = summary
                            r.xadd('incidents.enriched', alert, maxlen=200)
                            print(f"[NLP Enriched] [{alert.get('severity')}] {alert.get('pod')}: {summary}")
                        except Exception as alert_err:
                            print(f"[NLP] Error processing alert {rec_id}: {alert_err}")
                        last_id = rec_id
        except (redis.exceptions.TimeoutError, TimeoutError):
            # Normal timeout when no new incidents arrive during the block window
            pass
        except Exception as e:
            print(f"[NLP] Stream read error: {e}")
            time.sleep(2)
