"""
Visualization Planner

Given a natural language question, classifies it into one of two pipelines
and generates the appropriate visualization artifact:

  Pipeline 1 — Historical (TimescaleDB → Vanna SQL → DataFrame → matplotlib SVG code)
  Pipeline 2 — Realtime   (InfluxDB schema → Grafana panel config JSON)
"""

import json
import logging
from typing import Optional

import pandas as pd

from .utils import clean_markdown_code_blocks

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema Introspection
# ---------------------------------------------------------------------------

class SchemaIntrospector:
    """Pulls live schema information from TimescaleDB and InfluxDB."""

    def get_timescaledb_schema(self, config) -> str:
        """
        Connect to TimescaleDB and return a DDL-like schema string
        covering all public tables, with hypertables annotated.

        Args:
            config: GrafanaConfig with timescaledb_* fields.

        Returns:
            Multi-line schema string for use in LLM prompts and Vanna training.

        Raises:
            Exception: If connection fails.
        """
        import psycopg2

        conn = psycopg2.connect(
            host=config.timescaledb_host,
            port=config.timescaledb_port,
            dbname=config.timescaledb_db,
            user=config.timescaledb_user,
            password=config.timescaledb_password,
            connect_timeout=10,
        )
        try:
            with conn.cursor() as cur:
                # Fetch all columns for public tables
                cur.execute(
                    """
                    SELECT
                        c.table_name,
                        c.column_name,
                        c.data_type,
                        c.is_nullable
                    FROM information_schema.columns c
                    JOIN information_schema.tables t
                      ON c.table_name = t.table_name
                     AND c.table_schema = t.table_schema
                    WHERE c.table_schema = 'public'
                      AND t.table_type = 'BASE TABLE'
                    ORDER BY c.table_name, c.ordinal_position
                    """
                )
                rows = cur.fetchall()

                # Detect hypertables (TimescaleDB time-series tables)
                hypertables = set()
                try:
                    cur.execute(
                        "SELECT hypertable_name FROM timescaledb_information.hypertables"
                    )
                    hypertables = {r[0] for r in cur.fetchall()}
                except Exception:
                    pass  # timescaledb_information may not exist on plain postgres

        finally:
            conn.close()

        if not rows:
            return ""

        # Group columns by table and render DDL-like text
        tables: dict[str, list] = {}
        for table_name, col_name, data_type, nullable in rows:
            tables.setdefault(table_name, []).append((col_name, data_type, nullable))

        lines = []
        for table_name, columns in tables.items():
            tag = " -- (hypertable / time-series)" if table_name in hypertables else ""
            lines.append(f"TABLE {table_name}{tag} (")
            for col_name, data_type, nullable in columns:
                null_str = "" if nullable == "YES" else " NOT NULL"
                lines.append(f"    {col_name} {data_type.upper()}{null_str},")
            lines[-1] = lines[-1].rstrip(",")  # remove trailing comma on last col
            lines.append(");")
            lines.append("")

        return "\n".join(lines).strip()

    def get_influxdb_schema(self, config) -> Optional[str]:
        """
        Connect to InfluxDB and return a schema string covering all
        measurements, their fields and tags.

        Args:
            config: GrafanaConfig with influxdb_* fields.

        Returns:
            Schema string, or None if InfluxDB is unreachable / not configured.
        """
        if not config.influxdb_token or not config.influxdb_bucket:
            logger.warning("InfluxDB token or bucket not configured — skipping introspection")
            return None

        try:
            from influxdb_client import InfluxDBClient
        except ImportError:
            logger.error("influxdb-client not installed")
            return None

        try:
            client = InfluxDBClient(
                url=config.influxdb_url,
                token=config.influxdb_token,
                org=config.influxdb_org,
                timeout=10_000,
            )
            query_api = client.query_api()
            bucket = config.influxdb_bucket

            # List measurements
            measurements_flux = f'''
import "influxdata/influxdb/schema"
schema.measurements(bucket: "{bucket}")
'''
            measurements_result = query_api.query(measurements_flux)
            measurements = [
                record.get_value()
                for table in measurements_result
                for record in table.records
            ]

            if not measurements:
                client.close()
                return None

            lines = []
            for measurement in measurements:
                lines.append(f"MEASUREMENT {measurement}")

                # Tags — fetch keys then their concrete values
                tags_flux = f'''
import "influxdata/influxdb/schema"
schema.tagKeys(bucket: "{bucket}", predicate: (r) => r._measurement == "{measurement}")
'''
                tags_result = query_api.query(tags_flux)
                tag_keys = [
                    record.get_value()
                    for table in tags_result
                    for record in table.records
                    if not record.get_value().startswith("_")
                ]
                if tag_keys:
                    lines.append("  Tags:")
                    for tag_key in tag_keys:
                        values_flux = f'''
import "influxdata/influxdb/schema"
schema.tagValues(bucket: "{bucket}", tag: "{tag_key}", predicate: (r) => r._measurement == "{measurement}")
'''
                        try:
                            values_result = query_api.query(values_flux)
                            values = [
                                record.get_value()
                                for table in values_result
                                for record in table.records
                            ][:20]  # cap at 20 to keep schema concise
                            if values:
                                lines.append(
                                    f"    {tag_key} (values: {', '.join(str(v) for v in values)})"
                                )
                            else:
                                lines.append(f"    {tag_key}")
                        except Exception:
                            lines.append(f"    {tag_key}")

                # Fields
                fields_flux = f'''
import "influxdata/influxdb/schema"
schema.fieldKeys(bucket: "{bucket}", predicate: (r) => r._measurement == "{measurement}")
'''
                fields_result = query_api.query(fields_flux)
                fields = [
                    record.get_value()
                    for table in fields_result
                    for record in table.records
                ]
                if fields:
                    lines.append(f"  Fields: {', '.join(fields)}")

                lines.append("")

            client.close()
            return "\n".join(lines).strip()

        except Exception as e:
            logger.warning(f"InfluxDB introspection failed: {e}")
            return None


# ---------------------------------------------------------------------------
# Visualization Planner
# ---------------------------------------------------------------------------

class VisualizationPlanner:
    """
    Classifies a natural language question into a visualization pipeline
    and returns the appropriate artifact.

    Pipeline 1 (Historical):
        Vanna → SQL → DataFrame → LLM → matplotlib SVG code

    Pipeline 2 (Realtime):
        LLM → Grafana panel config JSON
    """

    def __init__(self, vn, ai_client, model: str, config):
        """
        Args:
            vn:        Initialized Vanna instance (connected to TimescaleDB).
            ai_client: OpenAI-compatible client (from utils.create_openai_compatible_client).
            model:     Model name string.
            config:    GrafanaConfig instance.
        """
        self.vn = vn
        self.client = ai_client
        self.model = model
        self.config = config
        self.introspector = SchemaIntrospector()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(self, question: str) -> dict:
        """
        Main entry point. Introspects schemas, classifies the question,
        then runs the appropriate pipeline.

        Args:
            question: Natural language question from the user.

        Returns:
            Dict with keys: pipeline, sql, code_render_svg, grafana_config, reasoning.
            On error: {"error": "..."}.
        """
        # 1. Introspect schemas
        logger.info("[planner] Introspecting schemas…")
        ts_schema = self._safe_get_ts_schema()
        influx_schema = self._safe_get_influx_schema()

        # 2. Classify
        logger.info("[planner] Classifying question…")
        classification = self._classify(question, ts_schema, influx_schema)
        pipeline = classification.get("pipeline", "historical")
        reasoning = classification.get("reasoning", "")
        logger.info(f"[planner] Pipeline={pipeline} confidence={classification.get('confidence')} — {reasoning}")

        # 3. Route
        if pipeline == "realtime":
            if influx_schema is None:
                return {"error": "realtime pipeline unavailable"}
            return self._run_realtime(question, influx_schema, reasoning)
        else:
            return self._run_historical(question, ts_schema, reasoning)

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    def _safe_get_ts_schema(self) -> str:
        try:
            schema = self.introspector.get_timescaledb_schema(self.config)
            logger.info("[planner] TimescaleDB schema fetched")
            return schema
        except Exception as e:
            logger.warning(f"[planner] TimescaleDB introspection failed: {e}")
            return ""

    def _safe_get_influx_schema(self) -> Optional[str]:
        try:
            schema = self.introspector.get_influxdb_schema(self.config)
            if schema:
                logger.info("[planner] InfluxDB schema fetched")
            return schema
        except Exception as e:
            logger.warning(f"[planner] InfluxDB introspection failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Pipeline 1 — Historical
    # ------------------------------------------------------------------

    def _run_historical(self, question: str, ts_schema: str, reasoning: str) -> dict:
        logger.info("[planner] Running historical pipeline…")

        # Vanna: question → SQL → DataFrame
        try:
            sql = self.vn.generate_sql(question)
            logger.info(f"[planner] Vanna SQL: {sql}")
            df = self.vn.run_sql(sql)
        except Exception as e:
            return {"error": f"SQL generation/execution failed: {e}"}

        if df is None or (hasattr(df, "empty") and df.empty):
            return {"error": "SQL query returned no data"}

        # Build df profile for LLM
        profile = self._profile_df(df)

        # LLM: question + profile → matplotlib code
        code = self._generate_matplotlib_code(question, profile)

        # Execute matplotlib code → rendered SVG string
        svg = self._execute_matplotlib_code(code, df)

        return {
            "pipeline": "historical",
            "code_render_svg": svg,
            "panel_embed_url": None,
            "reasoning": reasoning,
        }

    # ------------------------------------------------------------------
    # Pipeline 2 — Realtime
    # ------------------------------------------------------------------

    def _run_realtime(self, question: str, influx_schema: str, reasoning: str) -> dict:
        logger.info("[planner] Running realtime pipeline…")
        grafana_config = self._generate_grafana_config(question, influx_schema)

        # Push to remote Grafana and get embed URL
        from .grafana.pusher import GrafanaPusher

        pusher = GrafanaPusher(self.config)
        push_result = pusher.push(grafana_config)

        return {
            "pipeline": "realtime",
            "code_render_svg": None,
            "panel_embed_url": push_result.get("panel_embed_url"),
            "reasoning": reasoning,
        }

    # ------------------------------------------------------------------
    # LLM calls
    # ------------------------------------------------------------------

    def _classify(self, question: str, ts_schema: str, influx_schema: Optional[str]) -> dict:
        """
        LLM call: classify question into 'historical' or 'realtime'.

        Returns dict with keys: pipeline, confidence, reasoning.
        Defaults to 'historical' on any failure.
        """
        influx_section = (
            f"InfluxDB schema (realtime measurements):\n{influx_schema}"
            if influx_schema
            else "InfluxDB: NOT AVAILABLE — do not classify as realtime."
        )

        system_prompt = (
            "You are a visualization pipeline classifier for a backend observability system.\n"
            "Classify the user's question into exactly one pipeline:\n\n"
            "  historical — questions about trends, averages, analytics, past performance,\n"
            "               comparisons over time, aggregations, historical data.\n"
            "  realtime   — questions about current status, live metrics, monitoring,\n"
            "               last N minutes/hour, real-time usage.\n\n"
            "RULE: When in doubt or confidence is low, always choose 'historical'.\n\n"
            "Return ONLY a JSON object with exactly these keys:\n"
            '  {"pipeline": "historical"|"realtime", "confidence": "high"|"low", "reasoning": "..."}\n'
            "No markdown, no explanation outside the JSON."
        )

        user_content = (
            f"Question: {question}\n\n"
            f"TimescaleDB schema (historical tables):\n{ts_schema or '(unavailable)'}\n\n"
            f"{influx_section}"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0,
                max_tokens=256,
            )
            raw = response.choices[0].message.content or ""
            cleaned = clean_markdown_code_blocks(raw, "json")
            result = json.loads(cleaned)
            if result.get("pipeline") not in ("historical", "realtime"):
                result["pipeline"] = "historical"
            return result
        except Exception as e:
            logger.warning(f"[planner] Classification LLM call failed: {e} — defaulting to historical")
            return {"pipeline": "historical", "confidence": "low", "reasoning": f"classification failed: {e}"}

    def _generate_matplotlib_code(self, question: str, df_profile: str) -> str:
        """
        LLM call: generate matplotlib code that renders an SVG from `df`.

        Returns Python source code as a string.
        """
        system_prompt = (
            "You are a Python data visualization expert.\n"
            "Generate Python matplotlib code to visualize the provided DataFrame `df`.\n\n"
            "STRICT REQUIREMENTS:\n"
            "1. Start with: import matplotlib.pyplot as plt\n"
            "2. Use the column names exactly as shown in the DataFrame profile.\n"
            "3. Label both axes and set a descriptive title.\n"
            "4. Do NOT call plt.show() or plt.close() anywhere in the code.\n"
            "5. End with EXACTLY these lines to export SVG:\n"
            "     import io\n"
            "     buf = io.StringIO()\n"
            "     plt.savefig(buf, format='svg', bbox_inches='tight')\n"
            "     svg_output = buf.getvalue()\n"
            "     plt.close()\n"
            "6. The variable `svg_output` MUST contain the final SVG string.\n"
            "7. Do NOT generate fake data — `df` is already populated.\n"
            "8. Return ONLY the Python code, no markdown fences, no explanation."
        )

        user_content = (
            f"Question: {question}\n\n"
            f"DataFrame profile:\n{df_profile}"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0,
                max_tokens=1024,
            )
            raw = response.choices[0].message.content or ""
            return clean_markdown_code_blocks(raw, "python")
        except Exception as e:
            raise RuntimeError(f"matplotlib code generation failed: {e}") from e

    def _generate_grafana_config(self, question: str, influx_schema: str) -> dict:
        """
        LLM call: generate a Grafana panel config dict for the question.

        Returns a dict ready to be serialized as JSON.
        """
        system_prompt = (
            "You are a Grafana dashboard configuration expert.\n"
            "Generate a single Grafana panel configuration for the given question.\n\n"
            "REQUIREMENTS:\n"
            "1. type must be 'timeseries'\n"
            "2. Choose measurement and field from the InfluxDB schema provided.\n"
            "3. Choose an appropriate time_range: 5m, 15m, 1h, or 6h.\n"
            "4. Tags must use this exact format:\n"
            '   [{"key": "tag_name", "operator": "==", "value": "some_value"}]\n'
            "   Valid operators: ==, !=, =~, !~\n"
            "   Use empty array [] if no specific filtering needed.\n"
            "5. Return ONLY a JSON object with exactly these keys:\n"
            '   {"type": "timeseries", "title": "...", "measurement": "...",\n'
            '    "field": "...", "time_range": "...", "tags": [...]}\n'
            "No markdown, no explanation outside the JSON."
        )

        user_content = (
            f"Question: {question}\n\n"
            f"InfluxDB schema:\n{influx_schema}"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0,
                max_tokens=512,
            )
            raw = response.choices[0].message.content or ""
            cleaned = clean_markdown_code_blocks(raw, "json")
            return json.loads(cleaned)
        except Exception as e:
            raise RuntimeError(f"Grafana config generation failed: {e}") from e

    # ------------------------------------------------------------------
    # Matplotlib execution
    # ------------------------------------------------------------------

    def _execute_matplotlib_code(self, code: str, df: pd.DataFrame) -> str:
        """
        Execute LLM-generated matplotlib code and return the rendered SVG string.

        Args:
            code: Python source code that produces an `svg_output` variable.
            df:   The DataFrame to visualize.

        Returns:
            SVG string.

        Raises:
            RuntimeError: If execution fails or svg_output is not produced.
        """
        import matplotlib
        matplotlib.use("Agg")

        namespace = {"df": df}
        try:
            exec(code, namespace)
        except Exception as e:
            raise RuntimeError(f"Matplotlib code execution failed: {e}") from e

        svg = namespace.get("svg_output")
        if not svg:
            raise RuntimeError("Matplotlib code executed but 'svg_output' variable not produced")

        logger.info(f"[planner] SVG rendered ({len(svg)} bytes)")
        return svg

    # ------------------------------------------------------------------
    # DataFrame profiling
    # ------------------------------------------------------------------

    def _profile_df(self, df: pd.DataFrame) -> str:
        """
        Build a compact text profile of a DataFrame for use in LLM prompts.
        Passes column names, types, sample rows, and basic stats — not full data.
        """
        lines = []
        lines.append(f"Shape: {df.shape[0]} rows × {df.shape[1]} cols")

        # Column types
        col_types = ", ".join(f"{col} ({dtype})" for col, dtype in df.dtypes.items())
        lines.append(f"Columns: {col_types}")

        # Sample rows (up to 5)
        sample = df.head(5).to_string(index=False, max_cols=20)
        lines.append(f"\nSample (first 5 rows):\n{sample}")

        # Numeric stats
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            stat_parts = []
            for col in numeric_cols[:6]:  # cap at 6 columns to keep prompt size reasonable
                col_data = df[col].dropna()
                if len(col_data) > 0:
                    stat_parts.append(
                        f"{col} — min: {col_data.min():.2f}, "
                        f"max: {col_data.max():.2f}, "
                        f"mean: {col_data.mean():.2f}"
                    )
            if stat_parts:
                lines.append("\nNumeric stats:\n" + "\n".join(stat_parts))

        return "\n".join(lines)
