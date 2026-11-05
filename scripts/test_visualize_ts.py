#!/usr/bin/env python3
"""
Test script for the historical visualization pipeline (TimescaleDB only).

Usage:
    set -a && source .env && set +a
    uv run python scripts/test_visualize_ts.py "Show average CPU usage over the last 7 days"

If no question is provided, uses a default question.
Outputs SVG chart to scripts/output/test_chart.svg
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent / "output"
DEFAULT_QUESTION = "Show average CPU usage per node"


def main():
    question = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else DEFAULT_QUESTION
    logger.info(f"Question: {question}")

    # 1. Config from env
    from text2sql2chart.grafana.config import GrafanaConfig

    config = GrafanaConfig.from_env()
    logger.info(
        f"TimescaleDB: {config.timescaledb_host}:{config.timescaledb_port}"
        f"/{config.timescaledb_db}"
    )

    # 2. Initialize Vanna
    from vanna.openai import OpenAI_Chat
    from vanna.chromadb import ChromaDB_VectorStore
    from text2sql2chart.utils import get_ai_provider_config, create_openai_compatible_client
    from text2sql2chart.visualize_planner import SchemaIntrospector, VisualizationPlanner

    class VannaPostgres(ChromaDB_VectorStore, OpenAI_Chat):
        def __init__(self, config=None):
            ChromaDB_VectorStore.__init__(self, config=config)
            OpenAI_Chat.__init__(self, config=config)

    provider, api_key, model = get_ai_provider_config()
    chromadb_path = str(Path(__file__).parent.parent / "data" / "chromadb_timescaledb")
    vn = VannaPostgres(config={"api_key": api_key, "model": model, "path": chromadb_path})
    vn.connect_to_postgres(
        host=config.timescaledb_host,
        dbname=config.timescaledb_db,
        user=config.timescaledb_user,
        password=config.timescaledb_password,
        port=config.timescaledb_port,
    )
    logger.info("Connected to TimescaleDB")

    # 3. Introspect and train
    introspector = SchemaIntrospector()
    ts_schema = introspector.get_timescaledb_schema(config)
    if not ts_schema:
        logger.error("No schema found — check database name and permissions")
        sys.exit(1)

    print("\n=== TimescaleDB Schema ===")
    print(ts_schema)
    print()

    vn.train(ddl=ts_schema)
    logger.info("Vanna trained with schema")

    # 4. Create planner and run
    ai_client, model_name = create_openai_compatible_client(api_key, provider)
    planner = VisualizationPlanner(vn, ai_client, model_name, config)

    logger.info("Running planner...")
    result = planner.plan(question)

    if "error" in result:
        logger.error(f"Planner error: {result['error']}")
        sys.exit(1)

    print("\n=== Result ===")
    print(f"Pipeline:  {result.get('pipeline')}")
    print(f"SQL:       {result.get('sql')}")
    print(f"Reasoning: {result.get('reasoning')}")

    code = result.get("code_render_svg")
    if not code:
        logger.warning("No matplotlib code returned")
        sys.exit(1)

    print(f"\n=== Generated Matplotlib Code ===\n{code}\n")

    # 5. Execute the code to render SVG
    logger.info("Executing matplotlib code...")
    sql = result["sql"]
    df = vn.run_sql(sql)

    if df is None or df.empty:
        logger.error("SQL returned no data — cannot render chart")
        sys.exit(1)

    print(f"DataFrame: {df.shape[0]} rows x {df.shape[1]} cols")
    print(df.head())

    import matplotlib
    matplotlib.use("Agg")

    namespace = {"df": df}
    try:
        exec(code, namespace)
    except Exception as e:
        logger.error(f"Matplotlib code execution failed: {e}")
        print("\nCode that failed:")
        for i, line in enumerate(code.splitlines(), 1):
            print(f"  {i:3d} | {line}")
        sys.exit(1)

    svg_output = namespace.get("svg_output")
    if not svg_output:
        logger.error("Code executed but 'svg_output' variable not found")
        sys.exit(1)

    # 6. Save SVG
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    svg_path = OUTPUT_DIR / "test_chart.svg"
    svg_path.write_text(svg_output)
    logger.info(f"SVG saved to {svg_path}")
    print(f"\nOpen in browser: file://{svg_path.resolve()}")


if __name__ == "__main__":
    main()
