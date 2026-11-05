"""
Grafana Dashboard Generator

Converts data from Vanna queries and Plotly charts into Grafana dashboards.
Supports multiple integration methods:
1. Grafana JSON dashboard generation (Schema Version 41 - Grafana 11.x/12.x compatible)
2. CSV export for Grafana CSV datasource plugin
3. JSON data export for Grafana JSON datasource plugin
4. SQLite datasource configuration
"""

import json
import os
import pandas as pd
import numpy as np
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder for numpy data types"""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        return super(NumpyEncoder, self).default(obj)


class GrafanaDashboardGenerator:
    """
    Generate Grafana-compatible dashboards from your data analysis results
    """

    def __init__(self):
        self.dashboard_version = 1
        self.datasource_uid = "datasource_uid"

    def create_grafana_dashboard(self,
                                 chart_results: List[Dict[str, Any]],
                                 title: str = "Data Analysis Dashboard",
                                 datasource_type: str = "json",
                                 output_dir: str = "grafana_output") -> Dict[str, Any]:
        """
        Create a complete Grafana dashboard JSON from chart results

        Args:
            chart_results: List of chart result dictionaries from multi_chart_agent
            title: Dashboard title
            datasource_type: Type of datasource ('json', 'csv', 'sqlite', 'postgres')
            output_dir: Output directory for dashboard and data files

        Returns:
            Grafana dashboard JSON object
        """

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        print(f"Creating Grafana dashboard: {title}")

        # Filter successful charts
        successful_charts = [r for r in chart_results if r.get('success', False)]

        if not successful_charts:
            print("No successful charts to convert to Grafana")
            return None

        # Create dashboard structure
        dashboard = {
            "dashboard": {
                "title": title,
                "uid": self._generate_uid(),
                "version": self.dashboard_version,
                "timezone": "browser",
                "schemaVersion": 41,  # Grafana 11.x/12.x compatible
                "tags": ["generated", "vanna", "data-analysis"],
                "refresh": "5m",
                "time": {
                    "from": "now-6h",
                    "to": "now"
                },
                "panels": [],
                "editable": True,
                "graphTooltip": 1,
                "links": []
            },
            "overwrite": True
        }

        # Add panels for each chart
        panel_id = 1
        row = 0

        for i, chart_result in enumerate(successful_charts):
            panel = self._create_panel_from_chart(
                chart_result,
                panel_id,
                row,
                datasource_type
            )

            if panel:
                dashboard["dashboard"]["panels"].append(panel)
                panel_id += 1

                # Calculate row position (2 panels per row)
                if (i + 1) % 2 == 0:
                    row += 12

        # Save dashboard JSON
        dashboard_path = os.path.join(output_dir, "grafana_dashboard.json")
        with open(dashboard_path, 'w', encoding='utf-8') as f:
            json.dump(dashboard, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

        print(f"✓ Grafana dashboard saved: {dashboard_path}")

        # Export data for each chart
        self._export_chart_data(successful_charts, output_dir, datasource_type)

        return dashboard

    def _create_panel_from_chart(self,
                                 chart_result: Dict[str, Any],
                                 panel_id: int,
                                 row: int,
                                 datasource_type: str) -> Dict[str, Any]:
        """
        Create a Grafana panel from a chart result
        """

        question = chart_result.get('question', f'Chart {panel_id}')
        chart_type = chart_result.get('chart_type', 'bar')
        df = chart_result.get('data')

        if df is None or df.empty:
            return None

        # Basic column typing hints
        string_cols = [col for col in df.columns if df[col].dtype == 'object' or df[col].dtype.name == 'category']
        numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]

        # Map chart types to Grafana visualizations
        mapped_viz = self._map_chart_type_to_grafana(chart_type)

        # Detect if data is timeseries or table format (dynamic detection)
        is_timeseries = self._is_time_series_data(df)
        target_type = "timeseries" if is_timeseries else "table"

        viz_type = mapped_viz

        # If the chart was mapped to a time-based viz but we lack real time, fall back gracefully.
        if not is_timeseries and mapped_viz in ["timeseries", "scatter", "heatmap"]:
            if len(string_cols) >= 1 and len(numeric_cols) >= 1:
                viz_type = "barchart"
            else:
                viz_type = "table"

        # If we DO have a time-ish column but chart is scatter, prefer a timeseries line when multiple metrics exist.
        if is_timeseries and mapped_viz == "scatter" and len(numeric_cols) >= 2:
            viz_type = "timeseries"

        # Calculate panel position (2 columns layout)
        col = 0 if panel_id % 2 == 1 else 12

        panel = {
            "id": panel_id,
            "title": question,  # Limit title length
            "type": viz_type,
            "gridPos": {
                "h": 12,
                "w": 12,
                "x": col,
                "y": row
            },
            "datasource": {
                "type": datasource_type,
                "uid": self.datasource_uid
            },
            "targets": [
                {
                    "refId": "A",
                    "target": f"chart_{panel_id}_data",
                    "type": target_type
                }
            ],
            "options": self._get_panel_options(chart_type, df),
            "fieldConfig": self._get_field_config(viz_type, df)
        }

        return panel

    def _get_field_config(self, viz_type: str, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate Grafana field configuration with proper color support
        Uses Grafana's standard best practices for colors
        """

        # Standard Grafana approach: Use palette-classic for multi-color support
        # This automatically assigns different colors to different series/categories
        field_config = {
            "defaults": {
                "custom": {},
                "color": {
                    "mode": "palette-classic"
                }
            }
        }

        # Add thresholds for specific visualization types that benefit from them
        # (e.g., stat panels, gauges, or conditional coloring)
        if viz_type in ['stat', 'gauge', 'bargauge']:
            field_config["defaults"]["thresholds"] = {
                "mode": "absolute",
                "steps": [
                    {"value": None, "color": "green"},
                    {"value": 80, "color": "red"}
                ]
            }

        return field_config

    def _map_chart_type_to_grafana(self, chart_type: str) -> str:
        """
        Map Plotly chart types to Grafana visualization types
        """

        mapping = {
            'bar': 'barchart',
            'line': 'timeseries',
            'scatter': 'scatter',
            'pie': 'piechart',
            'histogram': 'histogram',
            'box': 'barchart',  # Grafana doesn't have native box plot
            'heatmap': 'heatmap',
            'area': 'timeseries'
        }

        return mapping.get(chart_type.lower(), 'barchart')

    def _get_panel_options(self, chart_type: str, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get Grafana panel options based on chart type
        """

        if chart_type in ['bar', 'histogram']:
            return {
                "orientation": "horizontal",
                "showValue": "auto",
                "legend": {
                    "displayMode": "list",
                    "placement": "bottom"
                }
            }
        elif chart_type == 'pie':
            return {
                "pieType": "pie",
                "legend": {
                    "displayMode": "list",
                    "placement": "right"
                },
                "tooltip": {
                    "mode": "single"
                }
            }
        elif chart_type == 'line':
            return {
                "tooltip": {
                    "mode": "multi"
                },
                "legend": {
                    "displayMode": "list",
                    "placement": "bottom"
                }
            }
        else:
            return {}

    def _export_chart_data(self,
                          chart_results: List[Dict[str, Any]],
                          output_dir: str,
                          datasource_type: str):
        """
        Export chart data in various formats for Grafana datasources
        """

        data_dir = os.path.join(output_dir, "data")
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        for i, chart_result in enumerate(chart_results, 1):
            df = chart_result.get('data')
            if df is None or df.empty:
                continue

            base_filename = f"chart_{i}_data"

            # Export as CSV (for CSV datasource plugin)
            csv_path = os.path.join(data_dir, f"{base_filename}.csv")
            df.to_csv(csv_path, index=False)
            print(f"  ✓ Exported CSV: {csv_path}")

            # Export as JSON (for JSON datasource plugin)
            json_path = os.path.join(data_dir, f"{base_filename}.json")
            data_json = self._dataframe_to_grafana_json(df, chart_result)
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data_json, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
            print(f"  ✓ Exported JSON: {json_path}")

    def _dataframe_to_grafana_json(self,
                                   df: pd.DataFrame,
                                   chart_result: Dict[str, Any]):
        """
        Convert DataFrame to Grafana JSON API format

        Returns either table format (for categorical data) or timeseries format
        """
        # Detect if this is categorical or time-series data
        is_time_series = self._is_time_series_data(df)

        if is_time_series:
            return self._to_timeseries_format(df)
        else:
            # Transform data for multi-series visualization (enables multi-color)
            df_transformed = self._transform_for_multi_series(df)
            return self._to_table_format(df_transformed)

    def _transform_for_multi_series(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform DataFrame to enable multi-color visualization in bar charts

        Intelligently detects if data has a categorical grouping column (like gender, category, type)
        and pivots it so each group becomes a separate series (column) for multi-color display.

        Example:
            Input:  age_group | gender | avg_income
                    20-29     | female | 56860
                    20-29     | male   | 54426

            Output: age_group | female | male
                    20-29     | 56860  | 54426
        """
        # Need at least 3 columns: category, group, value
        if len(df.columns) < 3:
            return df

        # Find columns by type
        string_cols = [col for col in df.columns if df[col].dtype == 'object' or df[col].dtype.name == 'category']
        numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]

        # Need at least 2 string columns and 1+ numeric column for pivoting
        if len(string_cols) >= 2 and len(numeric_cols) >= 1:
            # Intelligent column selection for multi-column scenarios
            if len(string_cols) == 2:
                # Simple case: exactly 2 string columns
                index_col = string_cols[0]  # Primary category (e.g., age_group)
                pivot_col = string_cols[1]   # Grouping for colors (e.g., gender)
            else:
                # Complex case: 3+ string columns
                # Strategy: Use first column as index, last column as pivot (most common pattern)
                # Example: city | state | crime_type | count → index=city, pivot=crime_type
                index_col = string_cols[0]
                pivot_col = string_cols[-1]  # Last categorical column usually contains the grouping
                print(f"  ℹ Multi-column data detected: using '{index_col}' as index, '{pivot_col}' for grouping")

            value_col = numeric_cols[0]  # Value to display

            # Check if pivot_col has reasonable number of unique values
            # Increased limit: 2-20 (was 2-10) to handle more categories
            unique_values = df[pivot_col].nunique()
            if 2 <= unique_values <= 20:
                try:
                    # Auto-detect appropriate aggregation function based on column name
                    agg_func = self._detect_aggregation_function(value_col)

                    # Pivot the data
                    df_pivot = df.pivot_table(
                        index=index_col,
                        columns=pivot_col,
                        values=value_col,
                        aggfunc=agg_func
                    ).reset_index()

                    # Clean up column names
                    df_pivot.columns.name = None

                    print(f"  ℹ Transformed data for multi-color: {pivot_col} groups ({unique_values} categories) as separate series (agg={agg_func})")
                    return df_pivot
                except Exception as e:
                    print(f"  ⚠ Could not pivot data: {e}")
                    return df
            else:
                if unique_values > 20:
                    print(f"  ℹ Skipping pivot: {pivot_col} has {unique_values} categories (limit: 20 for readability)")
                return df

        return df

    def _detect_aggregation_function(self, column_name: str) -> str:
        """
        Intelligently detect appropriate aggregation function based on column name

        Returns appropriate aggregation: 'sum', 'mean', 'count', 'max', 'min'
        """
        col_lower = column_name.lower()

        # Average/Mean indicators: Check FIRST (before income/sum)
        # avg, average, mean, rate - these should always use mean
        if any(keyword in col_lower for keyword in ['avg', 'average', 'mean', 'rate', 'ratio', 'percent', 'score']):
            return 'mean'

        # Count indicators: count, number, quantity, freq
        if any(keyword in col_lower for keyword in ['count', 'number', 'qty', 'quantity', 'freq', 'occurrence']):
            return 'sum'  # Count values should be summed

        # Sum indicators: total, sum, amount, sales, revenue, cost
        if any(keyword in col_lower for keyword in ['total', 'sum', 'amount', 'sales', 'revenue', 'cost', 'expense', 'income']):
            return 'sum'

        # Max indicators: max, maximum, peak, highest
        if any(keyword in col_lower for keyword in ['max', 'maximum', 'peak', 'highest', 'top']):
            return 'max'

        # Min indicators: min, minimum, lowest
        if any(keyword in col_lower for keyword in ['min', 'minimum', 'lowest', 'bottom']):
            return 'min'

        # Default: use mean (safe default for most numeric data)
        return 'mean'

    def _extract_day_numbers(self, series: pd.Series) -> Optional[pd.Series]:
        """
        Try to extract integer day numbers from a column (e.g., 'Day 1', 'day_02', 3).
        Returns None if extraction fails for any non-null value.
        """
        def parse_val(val):
            if pd.isna(val):
                return None
            if isinstance(val, (int, float)) and not pd.isna(val):
                return int(val)
            s = str(val)
            match = re.search(r'(\d+)', s)
            if match:
                return int(match.group(1))
            return None

        parsed = series.apply(parse_val)
        if parsed.isnull().any():
            return None
        return parsed.astype(int)

    def _extract_hour_numbers(self, series: pd.Series) -> Optional[pd.Series]:
        """
        Extract hour-of-day (0-23) from values like '06', '6', 'hour_06'.
        Returns None if any non-null value can't be parsed.
        """
        def parse_val(val):
            if pd.isna(val):
                return None
            if isinstance(val, (int, float)) and not pd.isna(val):
                iv = int(val)
                return iv if 0 <= iv <= 23 else None
            s = str(val).strip()
            match = re.search(r'(\d{1,2})', s)
            if match:
                iv = int(match.group(1))
                return iv if 0 <= iv <= 23 else None
            return None

        parsed = series.apply(parse_val)
        if parsed.isnull().any():
            return None
        return parsed.astype(int)

    def _is_time_series_data(self, df: pd.DataFrame) -> bool:
        """
        Detect if DataFrame contains time-series data or categorical data
        """
        # Check for time/date columns
        for col in df.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in ['date', 'time', 'timestamp', 'datetime']):
                try:
                    pd.to_datetime(df[col])
                    return True
                except:
                    pass

        # Heuristic: treat "day" columns with numeric/parseable values as a time axis
        for col in df.columns:
            if 'day' in col.lower():
                if self._extract_day_numbers(df[col]) is not None:
                    return True
        # Heuristic: treat "hour" columns with parseable values as a time axis
        for col in df.columns:
            if 'hour' in col.lower():
                if self._extract_hour_numbers(df[col]) is not None:
                    return True

        # Check if first column is categorical
        if len(df.columns) > 0:
            first_col = df.columns[0]
            if df[first_col].dtype == 'object' or df[first_col].dtype.name == 'category':
                return False

        # If all columns are numeric, we can still render as timeseries with index-based time
        numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
        if len(numeric_cols) == len(df.columns) and len(numeric_cols) > 0:
            return True

        return False

    def _to_table_format(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Convert DataFrame to Grafana table format for categorical data
        """
        columns = []
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                col_type = "number"
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                col_type = "time"
            else:
                col_type = "string"

            columns.append({
                "text": col,
                "type": col_type
            })

        # Convert rows - preserve data types
        rows = []
        for _, row in df.iterrows():
            row_data = []
            for col_idx, val in enumerate(row):
                if pd.isna(val):
                    row_data.append(None)
                else:
                    col_name = df.columns[col_idx]
                    if pd.api.types.is_numeric_dtype(df[col_name]):
                        row_data.append(float(val))
                    elif pd.api.types.is_datetime64_any_dtype(df[col_name]):
                        row_data.append(pd.Timestamp(val).isoformat())
                    else:
                        row_data.append(str(val))
            rows.append(row_data)

        return {
            "columns": columns,
            "rows": rows,
            "type": "table"
        }

    def _to_timeseries_format(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Convert DataFrame to Grafana timeseries format with proper YYYYMMDD date handling
        """
        result = []

        # Find time/date column
        time_col = None
        for col in df.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in ['date', 'time', 'timestamp', 'datetime']):
                time_col = col
                break

        dt_series = None

        # Fallback: handle day-like columns (e.g., 'day', 'Day 1', 'day_3')
        if time_col is None:
            for col in df.columns:
                if 'day' in col.lower():
                    day_numbers = self._extract_day_numbers(df[col])
                    if day_numbers is not None:
                        # Use epoch + N days to build a sortable timeline
                        dt_series = pd.to_datetime(day_numbers - 1, unit='D', origin='1970-01-01')
                        time_col = col
                        break
        # Fallback: handle hour-of-day columns (e.g., 'hour', '06', 'hour_06')
        if time_col is None and dt_series is None:
            for col in df.columns:
                if 'hour' in col.lower():
                    hour_numbers = self._extract_hour_numbers(df[col])
                    if hour_numbers is not None:
                        dt_series = pd.to_datetime(hour_numbers, unit='h', origin='1970-01-01')
                        time_col = col
                        break

        # Parse datetime and get timestamps in milliseconds
        if time_col is None:
            # No time column, use indices
            timestamps = list(range(len(df)))
        else:
            if dt_series is None:
                # CRITICAL FIX: Check if integer dates in YYYYMMDD format (e.g., 20170101) FIRST
                # If we use default parser on integer 20170101, it interprets as nanoseconds = 20ms!
                if pd.api.types.is_integer_dtype(df[time_col]):
                    try:
                        # Try YYYYMMDD format for integers
                        dt_series = pd.to_datetime(df[time_col], format='%Y%m%d')
                    except:
                        pass

                # If not parsed yet, try default datetime parser
                if dt_series is None:
                    try:
                        dt_series = pd.to_datetime(df[time_col])
                    except:
                        pass

                # If still not parsed, try YYYYMMDD format as string
                if dt_series is None:
                    try:
                        dt_series = pd.to_datetime(df[time_col].astype(str), format='%Y%m%d')
                    except:
                        pass

            # Final fallback: use indices
            if dt_series is None:
                timestamps = list(range(len(df)))
            else:
                # Convert to Unix timestamps in milliseconds
                timestamps = (dt_series.astype(int) // 10**6).tolist()

            # CRITICAL FIX: Check if integer dates in YYYYMMDD format (e.g., 20170101) FIRST
            # If we use default parser on integer 20170101, it interprets as nanoseconds = 20ms!
            if pd.api.types.is_integer_dtype(df[time_col]):
                try:
                    # Try YYYYMMDD format for integers
                    dt_series = pd.to_datetime(df[time_col], format='%Y%m%d')
                except:
                    pass

            # If not parsed yet, try default datetime parser
            if dt_series is None:
                try:
                    dt_series = pd.to_datetime(df[time_col])
                except:
                    pass

            # If still not parsed, try YYYYMMDD format as string
            if dt_series is None:
                try:
                    dt_series = pd.to_datetime(df[time_col].astype(str), format='%Y%m%d')
                except:
                    pass

            # Final fallback: use indices
            if dt_series is None:
                timestamps = list(range(len(df)))
            else:
                # Convert to Unix timestamps in milliseconds
                timestamps = (dt_series.astype(int) // 10**6).tolist()

        # Find value columns (numeric columns that are NOT the time column)
        value_cols = []
        for col in df.columns:
            if col != time_col and pd.api.types.is_numeric_dtype(df[col]):
                value_cols.append(col)

        # If no value columns found, use all numeric columns (shouldn't happen normally)
        if not value_cols:
            value_cols = df.select_dtypes(include=['number']).columns.tolist()

        # Create datapoints for each value column
        for col in value_cols:
            datapoints = []
            for idx, value in enumerate(df[col]):
                if pd.notna(value):
                    datapoints.append([float(value), int(timestamps[idx])])

            # Use descriptive target name
            result.append({
                "target": col.replace('_', ' ').title(),
                "datapoints": datapoints
            })

        return result

    def _generate_uid(self) -> str:
        """Generate a unique ID for Grafana dashboard"""
        return str(uuid.uuid4())[:8]

    def create_datasource_config(self,
                                 datasource_type: str,
                                 database_path: str = None,
                                 output_dir: str = "grafana_output") -> Dict[str, Any]:
        """
        Create Grafana datasource configuration

        Args:
            datasource_type: 'sqlite', 'json', 'csv', 'postgres'
            database_path: Path to database file (for SQLite)
            output_dir: Output directory

        Returns:
            Datasource configuration JSON
        """

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        if datasource_type == 'sqlite':
            config = {
                "name": "SQLite-DataAnalysis",
                "type": "frser-sqlite-datasource",
                "access": "proxy",
                "uid": self.datasource_uid,
                "jsonData": {
                    "path": database_path or "/data/sql-murder-mystery.db"
                }
            }
        elif datasource_type == 'json':
            config = {
                "name": "JSON-DataAnalysis",
                "type": "simpod-json-datasource",
                "access": "proxy",
                "uid": self.datasource_uid,
                "url": "http://localhost:3000/grafana-data",
                "jsonData": {}
            }
        elif datasource_type == 'csv':
            config = {
                "name": "CSV-DataAnalysis",
                "type": "marcusolsson-csv-datasource",
                "access": "proxy",
                "uid": self.datasource_uid,
                "jsonData": {
                    "path": f"{output_dir}/data"
                }
            }
        else:
            config = {
                "name": "Default-DataAnalysis",
                "type": "testdata",
                "uid": self.datasource_uid
            }

        # Save datasource config
        config_path = os.path.join(output_dir, "datasource_config.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

        print(f"✓ Datasource config saved: {config_path}")

        return config

    def create_provisioning_files(self,
                                  dashboard_json: Dict[str, Any],
                                  datasource_config: Dict[str, Any],
                                  output_dir: str = "grafana_output"):
        """
        Create Grafana provisioning files for automatic dashboard/datasource setup

        These files can be placed in Grafana's provisioning directory:
        - /etc/grafana/provisioning/dashboards/
        - /etc/grafana/provisioning/datasources/
        """

        provisioning_dir = os.path.join(output_dir, "provisioning")
        os.makedirs(os.path.join(provisioning_dir, "dashboards"), exist_ok=True)
        os.makedirs(os.path.join(provisioning_dir, "datasources"), exist_ok=True)

        # Dashboard provisioning config
        dashboard_provisioning = {
            "apiVersion": 1,
            "providers": [
                {
                    "name": "Data Analysis Dashboards",
                    "type": "file",
                    "options": {
                        "path": os.path.join(provisioning_dir, "dashboards")
                    }
                }
            ]
        }

        dashboard_prov_path = os.path.join(provisioning_dir, "dashboards", "dashboard_provisioning.yaml")
        with open(dashboard_prov_path, 'w') as f:
            import yaml
            yaml.dump(dashboard_provisioning, f)

        # Copy dashboard JSON
        dashboard_file_path = os.path.join(provisioning_dir, "dashboards", "data_analysis.json")
        with open(dashboard_file_path, 'w', encoding='utf-8') as f:
            json.dump(dashboard_json, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

        # Datasource provisioning config
        datasource_provisioning = {
            "apiVersion": 1,
            "datasources": [datasource_config]
        }

        datasource_prov_path = os.path.join(provisioning_dir, "datasources", "datasource_provisioning.yaml")
        with open(datasource_prov_path, 'w') as f:
            import yaml
            yaml.dump(datasource_provisioning, f)

        print(f"✓ Provisioning files created in: {provisioning_dir}")
        print(f"  To use with Grafana, copy to:")
        print(f"    - {provisioning_dir}/dashboards/* → /etc/grafana/provisioning/dashboards/")
        print(f"    - {provisioning_dir}/datasources/* → /etc/grafana/provisioning/datasources/")


def convert_chart_results_to_grafana(chart_results: List[Dict[str, Any]],
                                     title: str = "Data Analysis Dashboard",
                                     datasource_type: str = "json",
                                     database_path: str = None,
                                     output_dir: str = "grafana_output") -> Dict[str, Any]:
    """
    Convenience function to convert chart results to Grafana dashboard

    Args:
        chart_results: Chart results from multi_chart_agent
        title: Dashboard title
        datasource_type: 'json', 'csv', 'sqlite', 'postgres'
        database_path: Path to database (for SQLite)
        output_dir: Output directory

    Returns:
        Dictionary with dashboard and datasource info
    """

    generator = GrafanaDashboardGenerator()

    # Create dashboard
    dashboard = generator.create_grafana_dashboard(
        chart_results,
        title=title,
        datasource_type=datasource_type,
        output_dir=output_dir
    )

    # Create datasource config
    datasource = generator.create_datasource_config(
        datasource_type=datasource_type,
        database_path=database_path,
        output_dir=output_dir
    )

    # Create provisioning files
    try:
        generator.create_provisioning_files(dashboard, datasource, output_dir)
    except ImportError:
        print("⚠ PyYAML not installed - skipping provisioning file generation")
        print("  Install with: pip install pyyaml")

    print("\n" + "="*60)
    print("GRAFANA INTEGRATION COMPLETE!")
    print("="*60)
    print(f"Dashboard JSON: {output_dir}/grafana_dashboard.json")
    print(f"Data files: {output_dir}/data/")
    print(f"Datasource config: {output_dir}/datasource_config.json")
    print("\nNext steps:")
    print("1. Install Grafana: https://grafana.com/grafana/download")
    print(f"2. Import dashboard JSON to Grafana")
    print(f"3. Configure datasource using datasource_config.json")
    print(f"4. View your data in Grafana!")
    print("="*60)

    return {
        "dashboard": dashboard,
        "datasource": datasource,
        "output_dir": output_dir
    }


if __name__ == "__main__":
    print("Grafana Dashboard Generator")
    print("Usage: from grafana_generator import convert_chart_results_to_grafana")
