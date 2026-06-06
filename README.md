# KubePulse AI

## Project Overview

KubePulse AI is a lightweight Kubernetes observability pipeline that collects metrics and logs, detects anomalies, correlates signals across pods, generates incidents, enriches them with an LLM, persists incidents to a local SQLite database, and exposes a REST + WebSocket API for a React dashboard.

Core ideas:
- Use Prometheus and Loki as telemetry sources.
- Normalize metrics into Redis streams.
- Run independent worker processes to analyze streams and publish incidents.
- Enrich incidents with an on-prem LLM (Ollama) and persist to SQLite.
- The dashboard consumes REST + WebSocket data to display incidents and correlation graphs.

## Components

- `collectors/normalizer.py` - queries Prometheus, normalizes metrics, writes to Redis streams.
- `agents/` - analysis workers (CPU, memory, storage, log) that read streams and publish incidents.
- `correlation/` - finds correlated pod metric pairs and stores graph info in Redis; `db_writer.py` persists metrics and incidents to `kubepulse.db`.
- `nlp/incident_intelligence.py` - calls the Ollama API to create short incident summaries.
- `api/main.py` - FastAPI server that serves incidents and graph JSON and exposes a WebSocket for live alerts.
- `dashboard/` - React app that visualizes the graph and incidents.
- `start_all.sh` - convenience script to bootstrap components (works in a Unix-like environment or WSL).

## Prerequisites

- OS: Linux, macOS, or Windows (WSL recommended for `start_all.sh`).
- Python 3.11+ installed.
- Docker (optional, recommended for Redis/Prometheus/Loki), or local Redis/Prometheus/Loki services.
- Redis accessible at `localhost:6379` by default.
- Prometheus and Loki accessible at the ports used by your cluster.
- Ollama, or an alternative LLM, reachable via HTTP if you want NLP enrichments.

## Quick Setup

1. Clone the repo and open the project root.
2. Create and activate a Python virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
```

3. Install Python dependencies:

```bash
pip install -r requirements.txt
```

4. Start Redis using Docker:

```bash
docker run -d --name redis -p 6379:6379 redis:7
```

5. Start the pipeline manually:

```bash
python collectors/normalizer.py &
python -m agents.cpu_worker &
python -m agents.memory_worker &
python -m agents.storage_worker &
python -m agents.log_worker &
python -m correlation.correlation_processor &
python -m correlation.db_writer &
python -m nlp.incident_intelligence &
```

6. Start the API server in another shell:

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

7. Run the dashboard UI:

```bash
cd dashboard
npm install
npm start
```

8. On Unix-like systems, you can try `start_all.sh` to automate startup. On Windows, use WSL or start components manually.

## Configuration

The project currently uses hardcoded endpoints for Redis, Prometheus, Loki, and Ollama. To adapt it:

- Edit the host and URL constants at the top of the relevant modules.
- Consider exporting these values as environment variables and loading them with `python-dotenv` or `os.environ`.

## Database

- The SQLite DB is `kubepulse.db` at the project root. It is excluded by `.gitignore`.
- For production or concurrent writes, consider migrating to Postgres or another client-server RDBMS.

## Troubleshooting

- Redis connection refused: ensure Redis is running on `localhost:6379` or update the host in `agents/base_worker.py`.
- Prometheus queries return no results: ensure Prometheus is scraping targets and the query expressions match your cluster metrics.
- Ollama API errors: confirm the Ollama server address in `nlp/incident_intelligence.py` and that the model is available.

## Recommended Improvements

- Add `pyproject.toml` for reproducible builds.
- Move configuration to environment variables and add a `config.py` loader.
- Add structured logging instead of `print` statements.
- Use Redis consumer groups for robust, scalable workers and offset management.
- Add `docker-compose.yml` to simplify running Redis, Prometheus, Loki, and a mock Ollama for local development.

## Contributing

1. Create an issue describing the change.
2. Open a pull request with a focused change and tests where applicable.