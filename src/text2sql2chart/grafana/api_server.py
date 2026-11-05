"""
JSON API Server for Grafana

Serves chart data to Grafana JSON datasource plugin.
Implements the simpod-json-datasource API endpoints.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from flask import Flask, jsonify, request, current_app
from flask_cors import CORS

from .config import GrafanaConfig, get_default_config
from .models import TimeSeries

logger = logging.getLogger(__name__)


class GrafanaAPIServer:
    """
    API server for serving chart data to Grafana

    Implements the JSON datasource API:
    - GET  /           : Health check
    - POST /search     : Return available metrics
    - POST /query      : Return time series data
    """

    def __init__(self, config: Optional[GrafanaConfig] = None):
        """
        Initialize API server

        Args:
            config: GrafanaConfig instance (uses defaults if not provided)
        """
        self.config = config or get_default_config()
        self.app = create_app(self.config)

    def run(self, host: Optional[str] = None, port: Optional[int] = None, debug: bool = False):
        """
        Run the Flask development server

        Args:
            host: Host to bind to (defaults to config)
            port: Port to bind to (defaults to config)
            debug: Enable debug mode
        """
        host = host or self.config.api_host
        port = port or self.config.api_port

        logger.info(f"Starting API server on {host}:{port}")
        logger.info(f"Data directory: {self.config.data_dir.absolute()}")
        logger.info(f"Data exists: {self.config.data_dir.exists()}")

        if self.config.data_dir.exists():
            files = list(self.config.data_dir.glob("*.json"))
            logger.info(f"Found {len(files)} JSON data files")
            for f in files:
                logger.info(f"  - {f.name}")
        else:
            logger.warning("WARNING: Data directory does not exist!")
            logger.warning(f"Expected: {self.config.data_dir.absolute()}")

        self.app.run(host=host, port=port, debug=debug)


def _init_vanna(config: GrafanaConfig):
    """
    Initialize a Vanna instance connected to TimescaleDB (PostgreSQL).
    Trains Vanna with the live schema via DDL.

    Called once at server startup; the result is stored in app.config['PLANNER'].

    Raises:
        Exception: If the database is unreachable or AI keys are missing.
    """
    from vanna.openai import OpenAI_Chat
    from vanna.chromadb import ChromaDB_VectorStore
    from ..utils import get_ai_provider_config, create_openai_compatible_client
    from ..visualize_planner import SchemaIntrospector, VisualizationPlanner

    class VannaPostgres(ChromaDB_VectorStore, OpenAI_Chat):
        def __init__(self, config=None):
            ChromaDB_VectorStore.__init__(self, config=config)
            OpenAI_Chat.__init__(self, config=config)

    provider, api_key, model = get_ai_provider_config()
    chromadb_path = str(Path(__file__).resolve().parent.parent.parent.parent / "data" / "chromadb_timescaledb")
    vn = VannaPostgres(config={"api_key": api_key, "model": model, "path": chromadb_path})
    vn.connect_to_postgres(
        host=config.timescaledb_host,
        dbname=config.timescaledb_db,
        user=config.timescaledb_user,
        password=config.timescaledb_password,
        port=config.timescaledb_port,
    )

    # Train Vanna with the live schema so it can generate accurate SQL
    ts_schema = SchemaIntrospector().get_timescaledb_schema(config)
    if ts_schema:
        vn.train(ddl=ts_schema)
        logger.info("[vanna] Trained with TimescaleDB schema")

    ai_client, model_name = create_openai_compatible_client(api_key, provider)
    return VisualizationPlanner(vn, ai_client, model_name, config)


def create_app(config: Optional[GrafanaConfig] = None) -> Flask:
    """
    Create Flask application with API endpoints

    Args:
        config: GrafanaConfig instance

    Returns:
        Configured Flask app
    """
    config = config or get_default_config()
    app = Flask(__name__)
    CORS(app)

    # Store config in app context
    app.config['GRAFANA_CONFIG'] = config

    # Initialize VisualizationPlanner once at startup (requires DB + AI key)
    try:
        planner = _init_vanna(config)
        app.config['PLANNER'] = planner
        logger.info("VisualizationPlanner initialized successfully")
    except Exception as e:
        app.config['PLANNER'] = None
        logger.warning(f"VisualizationPlanner init failed (database unreachable or API key missing?): {e}")

    @app.route('/')
    def health():
        """Health check endpoint"""
        data_exists = config.data_dir.exists()
        file_count = len(list(config.data_dir.glob("*.json"))) if data_exists else 0

        return jsonify({
            "status": "ok",
            "service": "text2sql2chart-api",
            "data_dir": str(config.data_dir),
            "data_exists": data_exists,
            "file_count": file_count
        })

    @app.route('/search', methods=['POST'])
    def search():
        """
        Return available chart targets (metrics)

        Called by Grafana to populate metric selection dropdown
        """
        try:
            if not config.data_dir.exists():
                logger.warning(f"Data directory not found: {config.data_dir}")
                return jsonify([])

            # Find all JSON data files
            files = [
                f.stem  # filename without .json extension
                for f in config.data_dir.glob("*.json")
            ]

            logger.info(f"[/search] Found {len(files)} charts: {files}")
            return jsonify(files)

        except Exception as e:
            logger.error(f"[/search] Error: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route('/query', methods=['POST'])
    def query():
        """
        Return time series data for requested targets

        Request format:
        {
            "targets": [
                {"target": "chart_1_data", "refId": "A", "type": "timeseries"}
            ],
            "range": {...},
            "interval": "1m"
        }

        Response format:
        [
            {
                "target": "series_name",
                "datapoints": [[value, timestamp], ...]
            }
        ]
        """
        try:
            data = request.get_json()
            targets = data.get('targets', [])

            logger.info(f"[/query] Request for {len(targets)} targets")
            logger.debug(f"[/query] Targets: {[t.get('target') for t in targets]}")

            result = []

            for target in targets:
                target_name = target.get('target', '')
                if not target_name:
                    logger.warning("[/query] Empty target name, skipping")
                    continue

                json_file = config.data_dir / f"{target_name}.json"

                logger.debug(f"[/query] Looking for: {json_file}")

                if json_file.exists():
                    with open(json_file, 'r') as f:
                        chart_data = json.load(f)

                    # Handle different data formats:
                    # 1. Table format (dict with columns/rows): {"type": "table", "columns": [...], "rows": [...]}
                    # 2. Time-series format (list): [{"target": "...", "datapoints": [[val, timestamp], ...]}]

                    if isinstance(chart_data, dict) and chart_data.get('type') == 'table':
                        # Table format - return as is for Grafana table panels
                        result.append(chart_data)
                        row_count = len(chart_data.get('rows', []))
                        logger.info(
                            f"[/query] Returning table with {row_count} rows "
                            f"for {target_name}"
                        )
                    elif isinstance(chart_data, list) and len(chart_data) > 0:
                        # Time-series format - add all series
                        for series in chart_data:
                            result.append(series)
                            datapoint_count = len(series.get('datapoints', []))
                            logger.info(
                                f"[/query] Returning {datapoint_count} datapoints "
                                f"for {series.get('target')}"
                            )
                    else:
                        logger.warning(
                            f"[/query] Unexpected data format in {json_file.name}: {type(chart_data)}"
                        )
                else:
                    logger.warning(f"[/query] File not found: {json_file}")

            logger.info(f"[/query] Total series returned: {len(result)}")
            return jsonify(result)

        except Exception as e:
            logger.error(f"[/query] Error: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route('/visualize', methods=['POST'])
    def visualize():
        """
        AI visualization planner endpoint.

        Request:
            POST /visualize
            {"question": "Show average CPU usage over the last 7 days"}

        Response (historical):
            {
                "pipeline": "historical",
                "code_render_svg": "<svg ...>",
                "panel_embed_url": null,
                "reasoning": "..."
            }

        Response (realtime):
            {
                "pipeline": "realtime",
                "code_render_svg": null,
                "panel_embed_url": "http://localhost:3000/d-solo/...",
                "reasoning": "..."
            }
        """
        planner = current_app.config.get('PLANNER')
        if planner is None:
            return jsonify({
                "error": "Visualization planner not available — check DB connection and API key"
            }), 503

        data = request.get_json(silent=True) or {}
        question = data.get('question', '').strip()
        if not question:
            return jsonify({"error": "question is required"}), 400

        try:
            result = planner.plan(question)
            return jsonify(result)
        except Exception as e:
            logger.error(f"[/visualize] Error: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    return app


def run_api_server(
    config: Optional[GrafanaConfig] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    debug: bool = False
):
    """
    Convenience function to run the API server

    Args:
        config: GrafanaConfig instance
        host: Host to bind to
        port: Port to bind to
        debug: Enable debug mode
    """
    server = GrafanaAPIServer(config)
    server.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run server with default config
    run_api_server(debug=True)
