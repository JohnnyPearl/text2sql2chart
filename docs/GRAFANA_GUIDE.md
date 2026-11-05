# Grafana Integration Guide

Complete guide to using Text2SQL2Chart with Grafana.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Overview

Text2SQL2Chart provides complete Grafana integration with zero manual configuration:

1. **Automatic Datasource Setup**: JSON datasource configured via API
2. **Automatic Dashboard Import**: Dashboard imported programmatically
3. **Docker Orchestration**: All services managed with docker-compose
4. **Health Monitoring**: Automatic service health checks

## Quick Start

### One Command Setup

```bash
# Everything automated
text2sql2chart grafana quick
```

This single command:
- ✅ Generates demo charts from your database
- ✅ Starts Docker services (API + Grafana)
- ✅ Waits for services to be ready
- ✅ Configures datasource automatically
- ✅ Imports dashboard automatically
- ✅ Opens your browser to the dashboard

### Step-by-Step Manual Process

If you prefer manual control:

```bash
# 1. Generate chart data
python examples/demo_grafana.py

# 2. Start services
docker-compose up -d

# 3. Wait for services (or use automation)
text2sql2chart grafana run

# 4. Open Grafana
open http://localhost:3000
```

## Architecture

### Components

```
┌─────────────────┐
│  Your Browser   │
└────────┬────────┘
         │ :3000
         ▼
┌─────────────────┐
│     Grafana     │ ◄── Dashboard + Datasource
└────────┬────────┘     Auto-configured
         │ API Calls
         ▼
┌─────────────────┐
│   API Server    │ ◄── Flask JSON API
└────────┬────────┘     (simpod-json-datasource)
         │
         ▼
┌─────────────────┐
│  Chart Data     │ ◄── Generated JSON files
│  (JSON files)   │     (Grafana format)
└─────────────────┘
```

### Data Flow

1. **Chart Generation**:
   - AI analyzes database
   - Generates SQL queries
   - Creates visualizations
   - Exports to JSON (Grafana format)

2. **API Server**:
   - Serves JSON data
   - Implements simpod-json-datasource API
   - Handles `/search` and `/query` endpoints

3. **Grafana**:
   - Loads datasource (auto-configured)
   - Loads dashboard (auto-imported)
   - Queries API for data
   - Renders visualizations

## Configuration

### Environment Variables

```bash
# Grafana settings
GRAFANA_URL=http://localhost:3000
GRAFANA_USER=<your-grafana-user>
GRAFANA_PASSWORD=<your-grafana-password>

# API server settings
API_HOST=0.0.0.0
API_PORT=5000
API_URL_INTERNAL=http://api-server:5000  # Docker network
API_URL_EXTERNAL=http://localhost:5000   # Host access

# Data paths
DATA_DIR=quick_grafana_output/grafana/data
DASHBOARD_FILE=quick_grafana_output/grafana/grafana_dashboard.json

# Logging
LOG_LEVEL=INFO
DEBUG=false
```

### Python Configuration

```python
import os
from text2sql2chart.grafana import GrafanaConfig

config = GrafanaConfig(
    grafana_url="http://localhost:3000",
    grafana_user=os.environ["GRAFANA_USER"],
    grafana_password=os.environ["GRAFANA_PASSWORD"],
    api_port=5000,
    data_dir="path/to/data",
    log_level="DEBUG"
)
```

## API Endpoints

The API server implements these endpoints:

### GET `/`

Health check endpoint.

```bash
curl http://localhost:5000/
```

Response:
```json
{
  "status": "ok",
  "service": "text2sql2chart-api",
  "data_dir": "quick_grafana_output/grafana/data",
  "data_exists": true,
  "file_count": 3
}
```

### POST `/search`

Returns available metrics (chart names).

```bash
curl -X POST http://localhost:5000/search \
  -H "Content-Type: application/json" \
  -d '{}'
```

Response:
```json
["chart_1_data", "chart_2_data", "chart_3_data"]
```

### POST `/query`

Returns time series data.

```bash
curl -X POST http://localhost:5000/query \
  -H "Content-Type: application/json" \
  -d '{
    "targets": [
      {"target": "chart_1_data"}
    ]
  }'
```

Response:
```json
[
  {
    "target": "count",
    "datapoints": [
      [2.0, 0],
      [1.0, 1],
      ...
    ]
  }
]
```

## Troubleshooting

### Charts Show "No Data"

**Cause**: Panel visualization type incompatible with data format.

**Solution**:
1. Change panel type to "Table" to view raw data
2. Or convert indices to timestamps in data generation

### Datasource Connection Failed

**Cause**: API server not reachable from Grafana container.

**Solution**:
```bash
# Check both services are running
docker-compose ps

# Check API server logs
docker logs grafana-api-server

# Verify network connectivity
docker exec grafana-visualization curl http://api-server:5000/
```

### Dashboard Not Found

**Cause**: Dashboard wasn't imported or wrong UID.

**Solution**:
```bash
# Re-run automation
text2sql2chart grafana run

# Or manually check
curl -u "$GRAFANA_USER:$GRAFANA_PASSWORD" http://localhost:3000/api/dashboards/uid/YOUR_UID
```

### Docker Build Fails

**Cause**: Missing data directory or source files.

**Solution**:
```bash
# Generate data first
python examples/demo_grafana.py

# Verify files exist
ls -la quick_grafana_output/grafana/data/

# Rebuild
docker-compose up -d --build
```

### Services Won't Start

**Cause**: Port conflicts or Docker not running.

**Solution**:
```bash
# Check if ports are available
lsof -i :3000
lsof -i :5000

# Check Docker status
docker ps

# Stop conflicting services
text2sql2chart grafana stop
```

## Advanced Usage

### Custom Datasource URL

```python
from text2sql2chart.grafana import GrafanaConfig, GrafanaAutomation

config = GrafanaConfig(
    api_url_internal="http://my-api-server:8080"
)

automation = GrafanaAutomation(config)
automation.run()
```

### Multiple Datasources

```python
# Configure multiple datasources
datasources = [
    {"name": "DB1", "url": "http://api1:5000"},
    {"name": "DB2", "url": "http://api2:5000"},
]

for ds in datasources:
    config = GrafanaConfig(
        datasource_name=ds["name"],
        api_url_internal=ds["url"]
    )
    automation = GrafanaAutomation(config)
    automation.configure_datasource()
```

### Production Deployment

For production use:

1. **Use proper authentication**:
   ```bash
   export GRAFANA_PASSWORD="strong-password-here"
   ```

2. **Enable HTTPS**:
   - Add reverse proxy (nginx/traefik)
   - Configure SSL certificates

3. **Persistent storage**:
   ```yaml
   # docker-compose.yml
   services:
     grafana:
       volumes:
         - grafana-data:/var/lib/grafana
   volumes:
     grafana-data:
   ```

4. **Resource limits**:
   ```yaml
   services:
     api-server:
       deploy:
         resources:
           limits:
             cpus: '0.5'
             memory: 512M
   ```

## Best Practices

1. **Always validate data before visualization**
2. **Use environment variables for credentials**
3. **Monitor service health regularly**
4. **Keep Docker images updated**
5. **Backup dashboard configurations**
6. **Use version control for dashboards**

## Additional Resources

- [Grafana Documentation](https://grafana.com/docs/)
- [simpod-json-datasource](https://github.com/simPod/GrafanaJsonDatasource)
- [Docker Compose](https://docs.docker.com/compose/)
