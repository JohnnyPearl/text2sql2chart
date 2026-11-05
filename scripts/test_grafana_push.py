#!/usr/bin/env python3
"""
Test Grafana panel push and get embed URL.

Usage:
    set -a && source .env && set +a
    uv run python scripts/test_grafana_push.py
    uv run python scripts/test_grafana_push.py "My Panel Title"
    uv run python scripts/test_grafana_push.py --clean
"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main():
    from text2sql2chart.grafana.config import GrafanaConfig
    from text2sql2chart.grafana.pusher import GrafanaPusher

    config = GrafanaConfig.from_env()
    pusher = GrafanaPusher(config)

    if "--clean" in sys.argv:
        import requests
        resp = requests.delete(
            f"{config.grafana_url.rstrip('/')}/api/dashboards/uid/ai-viz-planner",
            auth=(config.grafana_user, config.grafana_password),
            timeout=10,
        )
        print("Dashboard deleted" if resp.status_code == 200 else f"Status: {resp.status_code}")
        return

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    title = " ".join(args) if args else "Test: CPU Usage (Last 1h)"

    result = pusher.push({
        "type": "timeseries",
        "title": title,
        "measurement": "cpu",
        "field": "usage_idle",
        "time_range": "1h",
        "tags": [],
    })

    if result.get("status") != "ok":
        print(f"FAIL: {result.get('error')}")
        sys.exit(1)

    print(f"\nDashboard:  {result['dashboard_url']}")
    print(f"Embed URL:  {result['panel_embed_url']}")
    print(f"\niframe:\n  {result['iframe_html']}")


if __name__ == "__main__":
    main()
