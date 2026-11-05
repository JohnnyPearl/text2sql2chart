# VizMon: Text2SQL2Chart, a Natural-Language Visualization Agent for HPC Monitoring

[![Paper DOI](https://img.shields.io/badge/DOI-10.3233%2FFAIA260739-blue)](https://doi.org/10.3233/FAIA260739)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

Official implementation of the visualization agent described in *A Smart Monitoring Architecture for HPC Clusters with an AI-Powered Natural Language Visualization Agent* (SoMeT 2026).

## Overview

VizMon is an LLM agent that turns natural-language questions about an HPC cluster into visualizations. Each question is first classified by its temporal scope and then routed to one of two pipelines. The **historical pipeline** handles trends and past behavior: it generates SQL with [Vanna.AI](https://vanna.ai/) (Text-to-SQL backed by a ChromaDB vector store), runs it against TimescaleDB, and has the LLM write matplotlib code that renders the result as an SVG chart. The **realtime pipeline** handles live status questions: the LLM generates a Grafana panel configuration over InfluxDB metrics, pushes it to Grafana, and returns a live embed URL. Both pipelines sit behind a single `POST /visualize` endpoint that returns a unified JSON response.

## Architecture

```
                        POST /visualize
                               │
                    ┌──────────┴──────────┐
                    │    LLM Classifier   │
                    └──────────┬──────────┘
                               │
             ┌─────────────────┴─────────────────┐
             │                                   │
    ┌────────┴────────┐                 ┌────────┴────────┐
    │   HISTORICAL    │                 │    REALTIME     │
    │    Pipeline     │                 │    Pipeline     │
    └────────┬────────┘                 └────────┬────────┘
             │                                   │
    ┌────────┴────────┐                 ┌────────┴────────┐
    │  Vanna.AI       │                 │  LLM generates  │
    │  (ChromaDB)     │                 │  Grafana panel  │
    │  generate SQL   │                 │  config JSON    │
    └────────┬────────┘                 └────────┬────────┘
             │                                   │
    ┌────────┴────────┐                 ┌────────┴────────┐
    │  TimescaleDB    │                 │  GrafanaPusher  │
    │  query →        │                 │  push to remote │
    │  DataFrame      │                 │  Grafana API    │
    └────────┬────────┘                 └────────┬────────┘
             │                                   │
    ┌────────┴────────┐                          │
    │  LLM generates  │                          │
    │  matplotlib     │                          │
    │  code → SVG     │                          │
    └────────┬────────┘                          │
             │                                   │
     code_render_svg                     panel_embed_url
```

## Results

On the public [VisEval](https://github.com/microsoft/VisEval) benchmark, the historical chart-generation core reaches a **78.3% pass rate** and a **3.46 composite quality score**, outperforming four reference systems. The monitoring substrate stays under **2% of a 32 GiB host**. See the paper for full details.

## Quick Start (local)

Everything below runs on `localhost`.

### 1. Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Docker
- An OpenAI API key (or a Gemini API key)

### 2. Install

```bash
git clone https://github.com/<your-org>/text2sql2chart.git
cd text2sql2chart

# Using uv (recommended)
uv pip install -e .

# Or using pip
pip install -e .
```

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env` and replace every placeholder (API key, database user/password, InfluxDB token, Grafana user/password). Then load it:

```bash
set -a && source .env && set +a
```

### 4. Start the data services

The historical pipeline needs TimescaleDB, and the realtime pipeline needs InfluxDB 2.x and Grafana. If you already run these, point the `.env` variables at them. For a local test setup:

```bash
# TimescaleDB (historical metrics)
docker run -d --name timescaledb -p 5432:5432 \
  -e POSTGRES_DB="$TIMESCALEDB_DB" \
  -e POSTGRES_USER="$TIMESCALEDB_USER" \
  -e POSTGRES_PASSWORD="$TIMESCALEDB_PASSWORD" \
  timescale/timescaledb:latest-pg16

# InfluxDB 2.x (realtime metrics)
docker run -d --name influxdb -p 8086:8086 \
  -e DOCKER_INFLUXDB_INIT_MODE=setup \
  -e DOCKER_INFLUXDB_INIT_USERNAME=<influx-admin-user> \
  -e DOCKER_INFLUXDB_INIT_PASSWORD=<influx-admin-password> \
  -e DOCKER_INFLUXDB_INIT_ORG="$INFLUXDB_ORG" \
  -e DOCKER_INFLUXDB_INIT_BUCKET="$INFLUXDB_BUCKET" \
  -e DOCKER_INFLUXDB_INIT_ADMIN_TOKEN="$INFLUXDB_TOKEN" \
  influxdb:2

# Grafana
docker run -d --name grafana -p 3000:3000 \
  -e GF_SECURITY_ADMIN_USER="$GRAFANA_USER" \
  -e GF_SECURITY_ADMIN_PASSWORD="$GRAFANA_PASSWORD" \
  grafana/grafana:latest
```

Then, in Grafana, add an **InfluxDB** datasource (query language: Flux) pointing at your InfluxDB instance. The realtime pipeline uses the first InfluxDB datasource it finds. Feed metrics into TimescaleDB and InfluxDB with your collector of choice (e.g. Telegraf).

### 5. Run the API server

```bash
uv run text2sql2chart serve --host 0.0.0.0 --port 5000
# short alias: uv run t2s2c serve --port 5000
```

On startup the server introspects the TimescaleDB schema and trains Vanna on it.

### 6. Query it

```bash
# Health check
curl http://localhost:5000/

# Historical question → SVG chart
curl -X POST http://localhost:5000/visualize \
  -H "Content-Type: application/json" \
  -d '{"question": "Show average CPU usage per node over the last 7 days"}'

# Realtime question → Grafana embed URL
curl -X POST http://localhost:5000/visualize \
  -H "Content-Type: application/json" \
  -d '{"question": "Show current GPU memory usage"}'
```

## API Reference

### `POST /visualize`

**Request**

```json
{ "question": "Show average CPU usage per node" }
```

**Response (historical)**

```json
{
  "pipeline": "historical",
  "code_render_svg": "<svg xmlns='http://www.w3.org/2000/svg' ...>...</svg>",
  "panel_embed_url": null,
  "reasoning": "This question asks about historical CPU usage trends..."
}
```

**Response (realtime)**

```json
{
  "pipeline": "realtime",
  "code_render_svg": null,
  "panel_embed_url": "http://localhost:3000/d-solo/ai-viz-planner/...?panelId=1&refresh=10s",
  "reasoning": "This question asks about current GPU status..."
}
```

**Error**

```json
{ "error": "SQL query returned no data" }
```

### `GET /`

Health check. Returns server status and data directory info.

## Configuration

All configuration is read from environment variables (see [.env.example](.env.example)). No credentials have defaults; set them in `.env`.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes* | — | OpenAI API key |
| `GEMINI_API_KEY` | Yes* | — | Gemini API key (if `AI_PROVIDER=gemini`) |
| `AI_PROVIDER` | No | `openai` | `openai` or `gemini` |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | OpenAI model name |
| `TIMESCALEDB_HOST` | No | `localhost` | TimescaleDB host |
| `TIMESCALEDB_PORT` | No | `5432` | TimescaleDB port |
| `TIMESCALEDB_DB` | Yes | — | Database name (e.g. `hpc_monitoring`) |
| `TIMESCALEDB_USER` | Yes | — | Database user |
| `TIMESCALEDB_PASSWORD` | Yes | — | Database password |
| `INFLUXDB_URL` | No | `http://localhost:8086` | InfluxDB URL |
| `INFLUXDB_TOKEN` | Yes† | — | InfluxDB API token |
| `INFLUXDB_ORG` | Yes† | — | InfluxDB organization (e.g. `my-org`) |
| `INFLUXDB_BUCKET` | Yes† | — | InfluxDB bucket (e.g. `metrics`) |
| `GRAFANA_URL` | No | `http://localhost:3000` | Grafana URL |
| `GRAFANA_USER` | Yes† | — | Grafana user |
| `GRAFANA_PASSWORD` | Yes† | — | Grafana password |
| `API_HOST` | No | `0.0.0.0` | API server bind host |
| `API_PORT` | No | `5000` | API server port |
| `LOG_LEVEL` | No | `INFO` | Logging level |

\* One of `OPENAI_API_KEY` or `GEMINI_API_KEY` is required.
† Required for the realtime pipeline.

## Datasets

### Alibaba Cluster Trace 2018

The SQLite demos and `text2sql2chart data import-alibaba` use machine-usage data from the public [Alibaba Cluster Trace v2018](https://github.com/alibaba/clusterdata/tree/master/cluster-trace-v2018). It is not included in this repository because of its size. To use it:

1. Download `machine_usage` from the link above (follow the instructions in that repository).
2. Aggregate it per day into cluster-wide time series at 10 s, 30 s and 300 s resolution, with columns `cpu_util_percent`, `mem_util_percent`, `net_in`, `net_out`, `disk_io_percent`.
3. Save the files under this layout:

   ```
   data/alibaba2018/day_<N>/machine_usage_day_<N>_grouped_10_seconds.csv
   data/alibaba2018/day_<N>/machine_usage_day_<N>_grouped_30_seconds.csv
   data/alibaba2018/day_<N>/machine_usage_day_<N>_grouped_300_seconds.csv
   ```

4. Import into SQLite:

   ```bash
   uv run text2sql2chart data import-alibaba --day-dir data/alibaba2018/day_1
   ```

### VisEval

The benchmark used for evaluation is available at [microsoft/VisEval](https://github.com/microsoft/VisEval).

## Project Structure

```
text2sql2chart/
├── src/text2sql2chart/
│   ├── cli/
│   │   ├── commands.py               # CLI entry point + serve command
│   │   └── data_cli.py               # Data import subcommands
│   ├── grafana/
│   │   ├── api_server.py             # Flask API (/visualize, /search, /query)
│   │   ├── pusher.py                 # Push panels to Grafana
│   │   ├── config.py                 # Configuration (env vars)
│   │   ├── automation.py             # Docker automation (legacy)
│   │   └── models.py                 # Data models
│   ├── visualize_planner.py          # SchemaIntrospector + VisualizationPlanner
│   ├── utils.py                      # AI provider config, helpers
│   ├── chart_agent.py                # Chart type recommendation
│   ├── database_analyzer.py          # Schema analysis
│   ├── data_import.py                # Alibaba trace → SQLite import
│   ├── question_generator.py         # Question generation
│   ├── query_transformer.py          # Query transformation
│   ├── multi_chart_analysis_agent.py # Multi-chart orchestrator
│   ├── multi_chart_agent.py          # Multi-chart creation
│   ├── grafana_generator.py          # Grafana dashboard export
│   └── dashboard_generator.py        # HTML dashboard generation
├── scripts/
│   ├── test_visualize_ts.py          # Smoke test: historical pipeline
│   ├── test_visualize_influx.py      # Smoke test: realtime pipeline
│   └── test_grafana_push.py          # Smoke test: Grafana push
├── examples/
│   ├── demo_grafana.py               # SQLite demo (multi-chart → Grafana)
│   └── retrain_vanna_alibaba.py      # Retrain Vanna on the Alibaba SQLite DB
├── docs/                             # Additional guides (Grafana, uv)
├── docker/api/                       # API server Dockerfile
├── data/                             # Local datasets (see "Datasets")
├── docker-compose.yml
├── .env.example                      # Environment template
├── pyproject.toml
├── LICENSE
└── README.md
```

## Development

```bash
uv pip install -e ".[dev]"

# Format (line length 100) and type-check
uv run black src/
uv run mypy src/

# Pipeline smoke tests (require running services and a loaded .env)
uv run python scripts/test_visualize_ts.py
uv run python scripts/test_visualize_influx.py
uv run python scripts/test_grafana_push.py
```

## Troubleshooting

- **Server hangs on startup**: TimescaleDB is unreachable. Check `TIMESCALEDB_HOST`/`TIMESCALEDB_PORT` and that the container is running.
- **`OPENAI_API_KEY environment variable not set`**: load `.env` with `set -a && source .env && set +a`.
- **InfluxDB 401 Unauthorized**: the token in `INFLUXDB_TOKEN` is invalid or expired. Create a new one in the InfluxDB UI (Load Data → API Tokens).
- **`No InfluxDB datasource found in Grafana`**: add an InfluxDB datasource in Grafana (see Quick Start step 4).

## Citation

If you use this code, please cite:

```bibtex
@inproceedings{dang2026vizmon,
  title     = {A Smart Monitoring Architecture for {HPC} Clusters with an {AI}-Powered Natural Language Visualization Agent},
  author    = {Dang, Ngoc-Phu and Le, Khanh and Nguyen, Viet-Hung and Pham, Thai-An and La-Quoc, Nhut-Huan and Thoai, Nam},
  booktitle = {New Trends in Intelligent Software Methodologies, Tools and Techniques (SoMeT 2026)},
  editor    = {Fujita, Hamido and Selamat, Ali and Mohamed, Farhan},
  series    = {Frontiers in Artificial Intelligence and Applications},
  volume    = {430},
  pages     = {193--202},
  publisher = {IOS Press},
  year      = {2026},
  doi       = {10.3233/FAIA260739}
}
```

## Acknowledgments

This work was carried out at the High Performance Computing Laboratory (HPCC), Faculty of Computer Science and Engineering, Ho Chi Minh City University of Technology (HCMUT), VNU-HCM, under the supervision of Assoc. Prof. Nam Thoai and Dr. Thanh-Dang Diep.

Built with [Vanna.AI](https://vanna.ai/), [Grafana](https://grafana.com/), [TimescaleDB](https://www.timescale.com/), [InfluxDB](https://www.influxdata.com/) and [Flask](https://flask.palletsprojects.com/).

## License

This project is released under the MIT License. See [LICENSE](LICENSE).
