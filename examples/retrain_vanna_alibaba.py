#!/usr/bin/env python
"""
Retrain Vanna on imported Alibaba 2018 cluster tables.

- Discovers all machine_usage_day_*_{10s,30s,300s} tables in the DB
- Trains Vanna with DDL for each table plus consolidated documentation and sample SQL
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from vanna.chromadb import ChromaDB_VectorStore
from vanna.openai import OpenAI_Chat


# --------------------------------------------------------------------------- #
# Data structures and discovery helpers
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class AlibabaTable:
    name: str
    day: int
    interval_seconds: int


TABLE_PATTERN = re.compile(r"machine_usage_day_(\d+)_(10s|30s|300s)$", re.IGNORECASE)
INTERVAL_LABEL = {"10s": 10, "30s": 30, "300s": 300}
INTERVAL_DOCS = {
    10: "10-second granularity (high resolution)",
    30: "30-second granularity (medium resolution)",
    300: "5-minute granularity (long-term trends)",
}


def discover_alibaba_tables(db_path: Path) -> List[AlibabaTable]:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    tables: List[AlibabaTable] = []
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        for (tbl,) in cur.fetchall():
            match = TABLE_PATTERN.match(tbl)
            if not match:
                continue
            day = int(match.group(1))
            interval = INTERVAL_LABEL[match.group(2)]
            tables.append(AlibabaTable(tbl, day, interval))

    tables.sort(key=lambda t: (t.day, t.interval_seconds))
    if not tables:
        raise RuntimeError(f"No Alibaba tables found in {db_path}")
    return tables


# --------------------------------------------------------------------------- #
# Vanna setup
# --------------------------------------------------------------------------- #

class MyVanna(ChromaDB_VectorStore, OpenAI_Chat):
    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        OpenAI_Chat.__init__(self, config=config)


# --------------------------------------------------------------------------- #
# Training content generators
# --------------------------------------------------------------------------- #

def ddl_for_table(table: AlibabaTable) -> str:
    description = INTERVAL_DOCS.get(table.interval_seconds, f"{table.interval_seconds}-second granularity")
    return f"""
-- Alibaba Cluster Machine Usage - {description}
-- Sampling interval: {table.interval_seconds} seconds
CREATE TABLE {table.name} (
    timestamp DATETIME PRIMARY KEY,  -- Absolute timestamp starting 2018-01-01 + (day-1)
    cpu_util_percent REAL,           -- CPU utilization percentage (0-100)
    mem_util_percent REAL,           -- Memory utilization percentage (0-100)
    net_in REAL,                     -- Network input traffic (bytes)
    net_out REAL,                    -- Network output traffic (bytes)
    disk_io_percent REAL             -- Disk I/O utilization percentage (0-100)
);
"""


def doc_block(tables: Sequence[AlibabaTable]) -> str:
    lines: List[str] = [
        "Alibaba Cluster Dataset (2018):",
        "- Daily machine resource utilization metrics; each day in its own table.",
        "- Start date for day_1: 2018-01-01; day_N starts at 2018-01-01 + (N-1 days).",
        "",
        "Tables:",
    ]
    for tbl in tables:
        lines.append(f"- {tbl.name}: {INTERVAL_DOCS.get(tbl.interval_seconds, tbl.interval_seconds)} (day_{tbl.day})")

    # Build example table picks
    first_table = tables[0]
    last_table = tables[-1]
    day1_10s = _pick_table(tables, day=1, interval=10) or first_table
    day1_30s = _pick_table(tables, day=1, interval=30) or first_table
    day2_300s = _pick_table(tables, day=2, interval=300) or last_table

    lines += [
        "",
        "Metrics:",
        "- cpu_util_percent (0-100), mem_util_percent (0-100), net_in (bytes), net_out (bytes), disk_io_percent (0-100)",
        "",
        "Example queries:",
        f"- SELECT * FROM {day1_10s.name} WHERE timestamp BETWEEN '2018-01-01 10:00:00' AND '2018-01-01 11:00:00';",
        f"- SELECT AVG(cpu_util_percent) FROM {day2_300s.name};",
        f"- SELECT timestamp, cpu_util_percent FROM {day1_30s.name} ORDER BY timestamp LIMIT 10;",
        f"- SELECT day_label, AVG(cpu_util_percent) AS avg_cpu FROM (",
        f"    SELECT 'day_' || {day1_10s.day} AS day_label, cpu_util_percent FROM {day1_10s.name}",
        f"    UNION ALL",
        f"    SELECT 'day_' || {last_table.day} AS day_label, cpu_util_percent FROM {last_table.name}",
        f") GROUP BY day_label;",
    ]
    return "\n".join(lines)


def _pick_table(tables: Sequence[AlibabaTable], day: Optional[int] = None, interval: Optional[int] = None) -> Optional[AlibabaTable]:
    for tbl in tables:
        if day is not None and tbl.day != day:
            continue
        if interval is not None and tbl.interval_seconds != interval:
            continue
        return tbl
    return None


# --------------------------------------------------------------------------- #
# Train orchestration
# --------------------------------------------------------------------------- #

def retrain_vanna(db_path: Path, api_key: str, model: Optional[str]) -> None:
    config = {"api_key": api_key}
    if model:
        config["model"] = model

    vn = MyVanna(config=config)
    tables = discover_alibaba_tables(db_path)

    print(f"Discovered {len(tables)} tables:")
    for t in tables:
        print(f"  - {t.name} (day {t.day}, {t.interval_seconds}s)")

    print("\nTraining DDL for each table...")
    for t in tables:
        vn.train(ddl=ddl_for_table(t))
    print("DDL training complete.")

    print("Training documentation...")
    vn.train(documentation=doc_block(tables))
    print("Documentation training complete.")

    print("\n✅ Vanna retraining finished.")


# --------------------------------------------------------------------------- #
# CLI entrypoint
# --------------------------------------------------------------------------- #

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Retrain Vanna on Alibaba 2018 multi-day tables.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--db",
        default="data/alibaba2018/alibaba_cluster.db",
        help="Path to the SQLite database containing machine_usage_day_* tables.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("VANNA_MODEL", "gpt-4o-mini"),
        help="Model name for Vanna/OpenAI.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENAI_API_KEY"),
        help="OpenAI API key. Falls back to OPENAI_API_KEY env var.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.api_key:
        raise SystemExit("OPENAI_API_KEY is required (pass via --api-key or env).")
    retrain_vanna(Path(args.db), api_key=args.api_key, model=args.model)


if __name__ == "__main__":
    main()
