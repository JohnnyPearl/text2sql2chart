# Quick Start Guide

Get up and running with Text2SQL2Chart in 5 minutes.

## Prerequisites

- Python 3.11+
- Docker & Docker Compose
- OpenAI API Key

## Step 1: Install

```bash
git clone https://github.com/yourusername/text2sql2chart.git
cd text2sql2chart
pip install -e .
```

## Step 2: Configure

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your OpenAI API key
# OPENAI_API_KEY=sk-your-key-here
```

## Step 3: Run

```bash
# One command to rule them all
text2sql2chart grafana quick
```

## Step 4: Access

Open your browser to: http://localhost:3000

Log in with the `GRAFANA_USER` / `GRAFANA_PASSWORD` values from your `.env`.

## What Just Happened?

The `quick` command:

1. ✅ Analyzed your database using AI
2. ✅ Generated intelligent SQL queries
3. ✅ Created 3 charts with appropriate visualizations
4. ✅ Started Docker containers (API server + Grafana)
5. ✅ Auto-configured Grafana datasource
6. ✅ Auto-imported dashboard
7. ✅ Opened your browser

## Next Steps

### View Service Status

```bash
text2sql2chart grafana status
```

### Stop Services

```bash
text2sql2chart grafana stop
```

### Restart Services

```bash
text2sql2chart grafana run
```

### View Logs

```bash
# API server logs
docker logs grafana-api-server

# Grafana logs
docker logs grafana-visualization
```

## Troubleshooting

### Command not found: text2sql2chart

```bash
# Reinstall in editable mode
pip install -e .

# Or use the module directly
python -m text2sql2chart.cli.commands grafana quick
```

### Port already in use

```bash
# Check what's using the ports
lsof -i :3000  # Grafana
lsof -i :5000  # API server

# Stop conflicting services
text2sql2chart grafana stop
```

### No data in charts

See [Grafana Integration Guide](GRAFANA_GUIDE.md#troubleshooting) for detailed troubleshooting.

## Learn More

- [Full Documentation](../README.md)
- [Grafana Integration Guide](GRAFANA_GUIDE.md)
- [API Reference](API_REFERENCE.md)
