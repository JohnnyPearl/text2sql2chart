#!/usr/bin/env python3
"""
Test script for the realtime visualization pipeline (InfluxDB → Grafana).

Usage:
    set -a && source .env && set +a
    uv run python scripts/test_visualize_influx.py "Show GPU memory usage"
    uv run python scripts/test_visualize_influx.py --schema-only
    uv run python scripts/test_visualize_influx.py --clean
"""

import sys
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_QUESTION = "Show GPU memory usage"


def main():
    from text2sql2chart.grafana.config import GrafanaConfig
    from text2sql2chart.visualize_planner import SchemaIntrospector

    config = GrafanaConfig.from_env()

    # --clean: delete test dashboard
    if "--clean" in sys.argv:
        import requests
        resp = requests.delete(
            f"{config.grafana_url.rstrip('/')}/api/dashboards/uid/ai-viz-planner",
            auth=(config.grafana_user, config.grafana_password),
            timeout=10,
        )
        print("Dashboard deleted" if resp.status_code == 200 else f"Status: {resp.status_code}")
        return

    # 1. Introspect InfluxDB schema
    print(f"InfluxDB: {config.influxdb_url}")
    print(f"Bucket:   {config.influxdb_bucket}")
    print(f"Org:      {config.influxdb_org}")
    print()

    introspector = SchemaIntrospector()
    influx_schema = introspector.get_influxdb_schema(config)

    if not influx_schema:
        print("FAIL: Could not introspect InfluxDB schema (check token/bucket/connectivity)")
        sys.exit(1)

    print("=== InfluxDB Schema ===")
    print(influx_schema)
    print()

    if "--schema-only" in sys.argv:
        return

    # 2. Generate Grafana panel config via LLM
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    question = " ".join(args) if args else DEFAULT_QUESTION
    print(f"Question: {question}")
    print()

    from text2sql2chart.utils import get_ai_provider_config, create_openai_compatible_client
    from text2sql2chart.visualize_planner import VisualizationPlanner

    provider, api_key, model = get_ai_provider_config()
    ai_client, model_name = create_openai_compatible_client(api_key, provider)

    # Create a minimal planner (no Vanna needed for realtime)
    planner = VisualizationPlanner(vn=None, ai_client=ai_client, model=model_name, config=config)
    grafana_config = planner._generate_grafana_config(question, influx_schema)

    print("=== Generated Grafana Config ===")
    print(json.dumps(grafana_config, indent=2))
    print()

    # 3. Show the Flux query that will be generated
    from text2sql2chart.grafana.pusher import GrafanaPusher
    pusher = GrafanaPusher(config)
    flux = pusher._build_flux_query(grafana_config)

    print("=== Flux Query ===")
    print(flux)
    print()

    # 4. Push to Grafana
    result = pusher.push(grafana_config)

    if result.get("status") != "ok":
        print(f"FAIL: {result.get('error')}")
        sys.exit(1)

    print("=== Push Result ===")
    print(f"Dashboard:  {result['dashboard_url']}")
    print(f"Embed URL:  {result['panel_embed_url']}")
    print(f"\niframe:\n  {result['iframe_html']}")


if __name__ == "__main__":
    main()
