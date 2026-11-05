"""
Data Import Module

Converts CSV files to SQLite databases with timestamp generation.
Supports Alibaba cluster time-series data and other CSV formats.
"""

import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import re
import logging

logger = logging.getLogger(__name__)

DAY_DIR_PATTERN = re.compile(r'day[_-]?(\d+)$', re.IGNORECASE)


def _extract_day_number(day_path: Path) -> int:
    """
    Extract day number from a directory name like "day_1" or "day-2".
    """
    match = DAY_DIR_PATTERN.search(day_path.name)
    if not match:
        raise ValueError(f"Could not determine day number from path: {day_path}")
    return int(match.group(1))


def _discover_day_directories(day_root: Path) -> List[Tuple[int, Path]]:
    """
    Accept either a specific day directory or a parent directory containing day_* folders.
    Returns a sorted list of (day_number, Path) tuples.
    """
    if not day_root.exists():
        raise FileNotFoundError(f"Day directory not found: {day_root}")

    if day_root.is_file():
        raise ValueError(f"Expected a directory but found a file: {day_root}")

    try:
        # If the provided path is already a day directory, just return it
        day_number = _extract_day_number(day_root)
        return [(day_number, day_root)]
    except ValueError:
        pass

    day_dirs: List[Tuple[int, Path]] = []
    for child in day_root.iterdir():
        if not child.is_dir():
            continue
        try:
            day_number = _extract_day_number(child)
            day_dirs.append((day_number, child))
        except ValueError:
            continue

    if not day_dirs:
        raise ValueError(f"No day_* directories found under: {day_root}")

    return sorted(day_dirs, key=lambda item: item[0])


def _build_alibaba_file_mappings(day_number: int) -> List[Tuple[str, str, int]]:
    """
    Build file and table mappings for a given day number.
    """
    day_label = f"day_{day_number}"
    return [
        (f'machine_usage_{day_label}_grouped_10_seconds.csv', f'machine_usage_{day_label}_10s', 10),
        (f'machine_usage_{day_label}_grouped_30_seconds.csv', f'machine_usage_{day_label}_30s', 30),
        (f'machine_usage_{day_label}_grouped_300_seconds.csv', f'machine_usage_{day_label}_300s', 300),
    ]


def generate_timestamps(start_datetime: str, num_rows: int, interval_seconds: int) -> pd.Series:
    """
    Generate timestamp series for time-series data

    Args:
        start_datetime: Start timestamp (e.g., '2018-01-01 00:00:00')
        num_rows: Number of timestamps to generate
        interval_seconds: Interval between timestamps in seconds

    Returns:
        Pandas Series of timestamps

    Example:
        >>> timestamps = generate_timestamps('2018-01-01 00:00:00', 5, 10)
        >>> len(timestamps)
        5
    """
    start = pd.to_datetime(start_datetime)
    return pd.date_range(start=start, periods=num_rows, freq=f'{interval_seconds}s')


def convert_alibaba_csv_to_sqlite(
    csv_file: Path,
    db_path: Path,
    table_name: str,
    start_datetime: str = '2018-01-01 00:00:00',
    interval_seconds: int = 10
) -> int:
    """
    Convert Alibaba cluster CSV to SQLite table with timestamps

    Args:
        csv_file: Path to CSV file
        db_path: Path to output SQLite database
        table_name: Name of table to create
        start_datetime: Start timestamp for series
        interval_seconds: Sampling interval in seconds

    Returns:
        Number of rows imported

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV format is invalid
    """
    logger.info(f"Converting {csv_file.name} → {table_name}")

    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    # Read CSV
    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        raise ValueError(f"Error reading CSV file: {e}")

    num_rows = len(df)
    logger.info(f"  Read {num_rows} rows")

    # Validate expected columns
    expected_cols = ['cpu_util_percent', 'mem_util_percent', 'net_in', 'net_out', 'disk_io_percent']
    missing_cols = [col for col in expected_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing columns in CSV: {missing_cols}")

    # Generate timestamps
    timestamps = generate_timestamps(start_datetime, num_rows, interval_seconds)
    df.insert(0, 'timestamp', timestamps)

    # Write to SQLite
    try:
        conn = sqlite3.connect(db_path)
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        conn.close()
    except Exception as e:
        raise RuntimeError(f"Error writing to SQLite: {e}")

    logger.info(f"  Created table {table_name} with {num_rows} rows")

    return num_rows


def import_alibaba_day_data(
    day_dir: str,
    output_db_path: str,
    start_date: str = '2018-01-01'
) -> Dict[str, any]:
    """
    Import one or more Alibaba day CSV directories into a single SQLite database.

    Args:
        day_dir: Path to a day directory (e.g., data/alibaba2018/day_1) or
                 a parent directory containing multiple day_* folders.
        output_db_path: Output database path.
        start_date: Start date for day_1 timestamps (YYYY-MM-DD). Subsequent
                    day timestamps are offset automatically.

    Returns:
        Dictionary with import statistics:
        {
            'tables_created': int,
            'total_rows': int,
            'errors': List[str],
            'day_details': List[Dict[str, any]]
        }

    Example:
        >>> stats = import_alibaba_day_data(
        ...     'data/alibaba2018/day_1',
        ...     'data/alibaba2018/alibaba_cluster.db'
        ... )
        >>> stats['tables_created']
        3
    """
    try:
        base_start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    except ValueError:
        raise ValueError(f"Invalid start_date format ({start_date}). Expected YYYY-MM-DD.")

    day_path = Path(day_dir)
    db_path = Path(output_db_path)
    day_directories = _discover_day_directories(day_path)

    # Ensure output directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    stats = {
        'tables_created': 0,
        'total_rows': 0,
        'errors': [],
        'day_details': []
    }

    print(f"\n{'='*70}")
    print(f"Importing Alibaba Cluster Data")
    print(f"{'='*70}")
    print(f"Source: {day_dir} ({len(day_directories)} day(s) detected)")
    print(f"Output: {output_db_path}")
    print(f"Start Date: {start_date}")
    print(f"{'='*70}\n")

    for day_number, day_folder in day_directories:
        day_label = f"day_{day_number}"
        day_start_date = (base_start_date + timedelta(days=day_number - 1)).strftime('%Y-%m-%d')
        file_mappings = _build_alibaba_file_mappings(day_number)
        day_stats = {
            'day': day_number,
            'tables_created': 0,
            'rows_imported': 0,
            'errors': []
        }

        print(f"--- Processing {day_label} ({day_start_date}) from {day_folder}")

        for csv_filename, table_name, interval in file_mappings:
            csv_file = day_folder / csv_filename

            if not csv_file.exists():
                error_msg = f"File not found for {day_label}: {csv_file}"
                print(f"⚠️  {error_msg}")
                stats['errors'].append(error_msg)
                day_stats['errors'].append(error_msg)
                continue

            try:
                rows = convert_alibaba_csv_to_sqlite(
                    csv_file=csv_file,
                    db_path=db_path,
                    table_name=table_name,
                    start_datetime=f"{day_start_date} 00:00:00",
                    interval_seconds=interval
                )
                stats['tables_created'] += 1
                stats['total_rows'] += rows
                day_stats['tables_created'] += 1
                day_stats['rows_imported'] += rows
                print(f"✅ {table_name}: {rows:,} rows imported\n")

            except Exception as e:
                error_msg = f"Error importing {csv_filename} for {day_label}: {e}"
                print(f"❌ {error_msg}\n")
                stats['errors'].append(error_msg)
                day_stats['errors'].append(error_msg)
                logger.error(error_msg, exc_info=True)

        stats['day_details'].append(day_stats)

    print(f"{'='*70}")
    print(f"Import Summary")
    print(f"{'='*70}")
    print(f"✅ Tables created: {stats['tables_created']}")
    print(f"✅ Total rows imported: {stats['total_rows']:,}")

    if stats['day_details']:
        print("\nPer-day results:")
        for day_result in stats['day_details']:
            print(f"  - day_{day_result['day']}: {day_result['tables_created']} tables, {day_result['rows_imported']:,} rows")

    if stats['errors']:
        print(f"\n⚠️  Errors encountered: {len(stats['errors'])}")
        for error in stats['errors']:
            print(f"    - {error}")

    print(f"{'='*70}\n")

    return stats


def _discover_alibaba_tables(db_path: Path) -> List[Tuple[str, int, Optional[int]]]:
    """
    Inspect a SQLite database for Alibaba machine usage tables.

    Returns a list of (table_name, interval_seconds, day_number_or_None).
    """
    if not db_path.exists():
        return []

    pattern = re.compile(r'machine_usage(?:_day_(\d+))?_(10s|30s|300s)$', re.IGNORECASE)
    interval_lookup = {'10s': 10, '30s': 30, '300s': 300}
    tables: List[Tuple[str, int, Optional[int]]] = []

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    for (table_name,) in cursor.fetchall():
        match = pattern.match(table_name)
        if not match:
            continue
        day_number = int(match.group(1)) if match.group(1) else None
        interval_suffix = match.group(2)
        tables.append((table_name, interval_lookup[interval_suffix], day_number))

    conn.close()
    return sorted(tables, key=lambda item: (item[2] if item[2] is not None else -1, item[1]))


def train_vanna_alibaba_schema(vanna_instance, db_path: str):
    """
    Train Vanna with Alibaba cluster schema information

    Args:
        vanna_instance: Vanna instance to train
        db_path: Path to Alibaba SQLite database

    Example:
        >>> from vanna.openai import OpenAI_Chat
        >>> from vanna.chromadb import ChromaDB_VectorStore
        >>>
        >>> class MyVanna(ChromaDB_VectorStore, OpenAI_Chat):
        ...     def __init__(self, config=None):
        ...         ChromaDB_VectorStore.__init__(self, config=config)
        ...         OpenAI_Chat.__init__(self, config=config)
        >>>
        >>> vn = MyVanna(config={'api_key': 'your-key', 'model': 'gpt-4o-mini'})
        >>> train_vanna_alibaba_schema(vn, 'data/alibaba2018/alibaba_cluster.db')
    """
    print("\n" + "="*70)
    print("🎓 Training Vanna on Alibaba Cluster Schema")
    print("="*70 + "\n")

    interval_descriptions = {
        10: '10-second granularity (high resolution)',
        30: '30-second granularity (medium resolution)',
        300: '5-minute granularity (low resolution, long-term trends)',
    }

    tables = _discover_alibaba_tables(Path(db_path))
    if not tables:
        tables = [
            ('machine_usage_10s', 10, None),
            ('machine_usage_30s', 30, None),
            ('machine_usage_300s', 300, None),
        ]
        logger.warning("No Alibaba tables detected in database; training fallback legacy schemas")

    doc_table_lines: List[str] = []

    for table_name, interval, day_number in tables:
        day_label = f"day_{day_number}" if day_number is not None else "day_1"
        description = interval_descriptions.get(interval, f"{interval}-second granularity")
        ddl = f"""
-- Alibaba Cluster Machine Usage - {description}
-- Sampling interval: {interval} seconds
CREATE TABLE {table_name} (
    timestamp DATETIME PRIMARY KEY,  -- Absolute timestamp starting 2018-01-01 + (day-1)
    cpu_util_percent REAL,           -- CPU utilization percentage (0-100)
    mem_util_percent REAL,           -- Memory utilization percentage (0-100)
    net_in REAL,                     -- Network input traffic (bytes)
    net_out REAL,                    -- Network output traffic (bytes)
    disk_io_percent REAL             -- Disk I/O utilization percentage (0-100)
);
"""
        try:
            vanna_instance.train(ddl=ddl)
            print(f"  ✓ Trained schema for {table_name}")
            doc_table_lines.append(f"- {table_name} ({description}, {day_label})")
        except Exception as e:
            logger.warning(f"  ⚠️  Error training {table_name}: {e}")

    day_numbers = sorted({d for _, _, d in tables if d is not None})
    table_docs = "\n".join(doc_table_lines) if doc_table_lines else "No tables discovered."
    days_doc_line = (
        f"- Days imported: {', '.join(str(day) for day in day_numbers)}"
        if day_numbers else "- Days imported: unknown (legacy tables)"
    )

    # Add comprehensive documentation
    documentation = f"""
Alibaba Cluster Dataset (2018):

Overview:
- Machine resource utilization metrics from Alibaba's production cluster
- Daily data stored in separate tables with explicit sampling intervals
- Start date for day_1: 2018-01-01; day_N starts at 2018-01-01 + (N-1 days)

Imported Tables:
{table_docs}

Metrics:
- cpu_util_percent: CPU utilization (0-100%)
- mem_util_percent: Memory utilization (0-100%)
- net_in: Inbound network traffic (bytes)
- net_out: Outbound network traffic (bytes)
- disk_io_percent: Disk I/O utilization (0-100%)

Time Range:
- Each table stores absolute timestamps; use day-specific tables for the desired window

Query Examples:
- "SELECT * FROM machine_usage_day_1_10s WHERE timestamp BETWEEN '2018-01-01 10:00:00' AND '2018-01-01 11:00:00'"
- "SELECT AVG(cpu_util_percent) FROM machine_usage_day_2_300s"
- "SELECT timestamp, cpu_util_percent FROM machine_usage_day_3_30s ORDER BY timestamp"

Notes:
- Choose tables based on both day and desired granularity
- Network metrics (net_in, net_out) are in bytes, not percentages
{days_doc_line}
"""

    try:
        vanna_instance.train(documentation=documentation)
        print(f"  ✓ Trained comprehensive documentation")
    except Exception as e:
        logger.warning(f"  ⚠️  Error training documentation: {e}")

    print("\n✅ Vanna training complete!")
    print("="*70 + "\n")


def verify_database(db_path: str) -> Dict[str, any]:
    """
    Verify SQLite database structure and contents

    Args:
        db_path: Path to SQLite database

    Returns:
        Dictionary with verification results
    """
    db_path_obj = Path(db_path)

    if not db_path_obj.exists():
        return {
            'valid': False,
            'error': f"Database file not found: {db_path}"
        }

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        # Get row counts and schemas
        table_info = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            row_count = cursor.fetchone()[0]

            cursor.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]

            table_info[table] = {
                'rows': row_count,
                'columns': columns
            }

        conn.close()

        return {
            'valid': True,
            'tables': tables,
            'table_info': table_info,
            'total_rows': sum(info['rows'] for info in table_info.values())
        }

    except Exception as e:
        return {
            'valid': False,
            'error': str(e)
        }
