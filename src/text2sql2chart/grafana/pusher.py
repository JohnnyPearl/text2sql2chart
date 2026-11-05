"""
Grafana Dashboard Pusher

Pushes panel configurations to a remote Grafana instance via HTTP API
and returns dashboard/panel embed URLs.
"""

import json
import logging
import time
from typing import Optional
from urllib.parse import urljoin

import requests

from .config import GrafanaConfig

logger = logging.getLogger(__name__)

DASHBOARD_TITLE = "AI Visualization Planner"
DASHBOARD_UID = "ai-viz-planner"


class GrafanaPusher:
    """Pushes Grafana panel configs to a remote Grafana instance."""

    def __init__(self, config: GrafanaConfig):
        self.config = config
        self.base_url = config.grafana_url.rstrip("/")
        self.auth = (config.grafana_user, config.grafana_password)
        self._datasource_uid: Optional[str] = None

    def _api(self, method: str, path: str, json_data: dict = None) -> requests.Response:
        url = f"{self.base_url}{path}"
        resp = requests.request(method, url, json=json_data, auth=self.auth, timeout=10)
        return resp

    def _get_influxdb_datasource_uid(self) -> Optional[str]:
        """Find the first InfluxDB datasource UID."""
        if self._datasource_uid:
            return self._datasource_uid

        resp = self._api("GET", "/api/datasources")
        if resp.status_code != 200:
            logger.error(f"Failed to list datasources: {resp.status_code} {resp.text}")
            return None

        for ds in resp.json():
            if ds.get("type") == "influxdb":
                self._datasource_uid = ds["uid"]
                logger.info(f"Found InfluxDB datasource: {ds['name']} (uid={ds['uid']})")
                return self._datasource_uid

        logger.warning("No InfluxDB datasource found in Grafana")
        return None

    VALID_OPS = {"==", "!=", "=~", "!~", "<", ">", "<=", ">="}

    def _build_flux_query(self, panel_config: dict) -> str:
        """Build a Flux query from the panel config."""
        bucket = self.config.influxdb_bucket or "metrics"
        measurement = panel_config.get("measurement", "")
        field = panel_config.get("field", "")
        time_range = panel_config.get("time_range", "1h")

        lines = [
            f'from(bucket: "{bucket}")',
            f"  |> range(start: -{time_range})",
            f'  |> filter(fn: (r) => r["_measurement"] == "{measurement}")',
            f'  |> filter(fn: (r) => r["_field"] == "{field}")',
        ]

        for tag in panel_config.get("tags", []):
            key = tag.get("key", "")
            value = str(tag.get("value", ""))
            op = tag.get("operator", "==")
            if not key:
                continue
            if op not in self.VALID_OPS:
                op = "=="
            key = key.replace('"', '\\"')
            value = value.replace('"', '\\"')
            if op in ("=~", "!~"):
                lines.append(f'  |> filter(fn: (r) => r["{key}"] {op} /{value}/)')
            else:
                lines.append(f'  |> filter(fn: (r) => r["{key}"] {op} "{value}")')

        lines.append("  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)")
        lines.append('  |> yield(name: "mean")')
        return "\n".join(lines)

    def _build_panel(self, panel_config: dict, panel_id: int, ds_uid: str) -> dict:
        """Build a Grafana panel JSON from a panel config."""
        flux_query = self._build_flux_query(panel_config)

        return {
            "id": panel_id,
            "type": panel_config.get("type", "timeseries"),
            "title": panel_config.get("title", "Untitled"),
            "gridPos": {"h": 9, "w": 24, "x": 0, "y": (panel_id - 1) * 9},
            "datasource": {"type": "influxdb", "uid": ds_uid},
            "targets": [
                {
                    "refId": "A",
                    "datasource": {"type": "influxdb", "uid": ds_uid},
                    "query": flux_query,
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "custom": {
                        "drawStyle": "line",
                        "lineInterpolation": "smooth",
                        "fillOpacity": 10,
                        "pointSize": 5,
                        "showPoints": "auto",
                    },
                    "unit": "short",
                },
                "overrides": [],
            },
            "options": {
                "tooltip": {"mode": "multi"},
                "legend": {"displayMode": "list", "placement": "bottom"},
            },
        }

    def push(self, panel_config: dict) -> dict:
        """
        Push a panel config to Grafana.

        Args:
            panel_config: Dict with keys: type, title, measurement, field, time_range, tags

        Returns:
            Dict with keys: dashboard_url, panel_embed_url, status
            On error: {"error": "..."}
        """
        ds_uid = self._get_influxdb_datasource_uid()
        if not ds_uid:
            return {"error": "No InfluxDB datasource found in Grafana"}

        # Get existing dashboard to append panels, or start fresh
        existing_panels = []
        resp = self._api("GET", f"/api/dashboards/uid/{DASHBOARD_UID}")
        if resp.status_code == 200:
            existing = resp.json().get("dashboard", {})
            existing_panels = existing.get("panels", [])

        next_id = max((p.get("id", 0) for p in existing_panels), default=0) + 1
        panel = self._build_panel(panel_config, next_id, ds_uid)
        all_panels = existing_panels + [panel]

        time_range = panel_config.get("time_range", "1h")
        dashboard = {
            "uid": DASHBOARD_UID,
            "title": DASHBOARD_TITLE,
            "panels": all_panels,
            "schemaVersion": 38,
            "version": 0,
            "refresh": "10s",
            "time": {"from": f"now-{time_range}", "to": "now"},
        }

        payload = {"dashboard": dashboard, "overwrite": True}

        resp = self._api("POST", "/api/dashboards/db", json_data=payload)
        if resp.status_code != 200:
            logger.error(f"Grafana push failed: {resp.status_code} {resp.text}")
            return {"error": f"Grafana API error: {resp.status_code} {resp.text}"}

        result = resp.json()
        dash_path = result.get("url", "")
        dash_url = f"{self.base_url}{dash_path}"

        # Solo embed URL uses /d-solo/ instead of /d/
        solo_path = dash_path.replace("/d/", "/d-solo/", 1)
        panel_embed_url = (
            f"{self.base_url}{solo_path}"
            f"?orgId=1&panelId={next_id}"
            f"&from=now-{time_range}&to=now"
            f"&refresh=10s&__feature.dashboardSceneSolo=true"
        )
        iframe_html = (
            f'<iframe src="{panel_embed_url}"'
            f' width="450" height="200" frameborder="0"></iframe>'
        )

        logger.info(f"Dashboard pushed: {dash_url}")
        logger.info(f"Panel embed URL: {panel_embed_url}")

        return {
            "dashboard_url": dash_url,
            "panel_embed_url": panel_embed_url,
            "iframe_html": iframe_html,
            "panel_id": next_id,
            "status": "ok",
        }
