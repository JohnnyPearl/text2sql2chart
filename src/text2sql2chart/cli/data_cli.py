"""
Data CLI Commands

Provides CLI interface for data import and management operations.
"""

import argparse
import logging
import sys
from pathlib import Path

from ..data_import import import_alibaba_day_data, verify_database

logger = logging.getLogger(__name__)


def data_command(parser: argparse.ArgumentParser):
    """
    Add data subcommands to parser

    Args:
        parser: ArgumentParser for data command
    """
    subparsers = parser.add_subparsers(
        title='data commands',
        description='Data import and management operations',
        dest='data_cmd',
        help='Data command to execute'
    )

    # Import Alibaba command
    import_parser = subparsers.add_parser(
        'import-alibaba',
        help='Import Alibaba cluster CSV data to SQLite',
        description='Convert Alibaba cluster time-series CSVs to SQLite database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import day_1 data with default settings
  text2sql2chart data import-alibaba --day-dir data/alibaba2018/day_1

  # Import with custom output path
  text2sql2chart data import-alibaba \\
      --day-dir data/alibaba2018/day_1 \\
      --output data/custom/alibaba.db

  # Import with custom start date
  text2sql2chart data import-alibaba \\
      --day-dir data/alibaba2018/day_1 \\
      --start-date 2018-01-15

Output:
  Creates SQLite database with 3 tables:
  - machine_usage_10s  (10-second intervals)
  - machine_usage_30s  (30-second intervals)
  - machine_usage_300s (5-minute intervals)
        """
    )
    import_parser.add_argument(
        '--day-dir',
        type=str,
        required=True,
        help='Directory containing day CSV files (e.g., data/alibaba2018/day_1)'
    )
    import_parser.add_argument(
        '--output',
        type=str,
        default='data/alibaba2018/alibaba_cluster.db',
        help='Output SQLite database path (default: data/alibaba2018/alibaba_cluster.db)'
    )
    import_parser.add_argument(
        '--start-date',
        type=str,
        default='2018-01-01',
        help='Start date for timestamp generation in YYYY-MM-DD format (default: 2018-01-01)'
    )
    import_parser.set_defaults(func=cmd_import_alibaba)

    # Verify database command
    verify_parser = subparsers.add_parser(
        'verify',
        help='Verify database structure and contents',
        description='Check SQLite database integrity and display schema information',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Verify Alibaba database
  text2sql2chart data verify --database data/alibaba2018/alibaba_cluster.db

  # Verify default database
  text2sql2chart data verify --database data/sql-murder-mystery.db
        """
    )
    verify_parser.add_argument(
        '--database',
        type=str,
        required=True,
        help='Path to database file to verify'
    )
    verify_parser.set_defaults(func=cmd_verify_database)

    # List databases command
    list_parser = subparsers.add_parser(
        'list',
        help='List available databases in data directory',
        description='Show all SQLite databases with table and row counts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  text2sql2chart data list

Output:
  Lists all .db files in data/ directory with:
  - Database path
  - Table names and counts
  - Total row counts
        """
    )
    list_parser.set_defaults(func=cmd_list_databases)


def cmd_import_alibaba(args):
    """
    Execute Alibaba import command

    Args:
        args: Parsed command-line arguments
    """
    logger.info("🚀 Starting Alibaba Cluster Data Import")

    # Validate day directory exists
    day_path = Path(args.day_dir)
    if not day_path.exists():
        logger.error(f"❌ Day directory not found: {args.day_dir}")
        logger.error(f"   Please ensure the directory exists and contains CSV files")
        sys.exit(1)

    if not day_path.is_dir():
        logger.error(f"❌ Path is not a directory: {args.day_dir}")
        sys.exit(1)

    # Validate start date format
    try:
        from datetime import datetime
        datetime.strptime(args.start_date, '%Y-%m-%d')
    except ValueError:
        logger.error(f"❌ Invalid date format: {args.start_date}")
        logger.error(f"   Expected format: YYYY-MM-DD (e.g., 2018-01-01)")
        sys.exit(1)

    try:
        stats = import_alibaba_day_data(
            day_dir=args.day_dir,
            output_db_path=args.output,
            start_date=args.start_date
        )

        if stats['errors']:
            logger.warning(f"\n⚠️  Import completed with {len(stats['errors'])} errors")
            logger.warning(f"   Database may be incomplete")
            sys.exit(1)
        else:
            logger.info("\n✅ Import successful!")
            logger.info(f"\nNext steps:")
            logger.info(f"  1. Set your OpenAI API key:")
            logger.info(f"     export OPENAI_API_KEY='your-key-here'")
            logger.info(f"")
            logger.info(f"  2. Generate visualizations:")
            logger.info(f"     text2sql2chart grafana generate \\")
            logger.info(f"         --database {args.output} \\")
            logger.info(f"         --prompt \"show cpu utilization in day 1\" \\")
            logger.info(f"         --charts 5")
            logger.info(f"")
            logger.info(f"  3. Open Grafana dashboard:")
            logger.info(f"     http://localhost:3000")
            logger.info(f"     (credentials: GRAFANA_USER / GRAFANA_PASSWORD from .env)")
            sys.exit(0)

    except Exception as e:
        logger.error(f"❌ Import failed: {e}", exc_info=True)
        sys.exit(1)


def cmd_verify_database(args):
    """
    Execute database verification command

    Args:
        args: Parsed command-line arguments
    """
    logger.info(f"🔍 Verifying database: {args.database}")
    logger.info("="*70)

    result = verify_database(args.database)

    if not result['valid']:
        logger.error(f"❌ Verification failed: {result['error']}")
        sys.exit(1)

    logger.info(f"✅ Database is valid\n")
    logger.info(f"Tables found: {len(result['tables'])}")
    logger.info(f"Total rows: {result['total_rows']:,}\n")

    logger.info("Table Details:")
    logger.info("-" * 70)

    for table, info in result['table_info'].items():
        logger.info(f"\n{table}")
        logger.info(f"  Rows: {info['rows']:,}")
        logger.info(f"  Columns ({len(info['columns'])}): {', '.join(info['columns'])}")

    logger.info("\n" + "="*70)
    logger.info("✅ Verification complete")


def cmd_list_databases(args):
    """
    List available databases in data directory

    Args:
        args: Parsed command-line arguments
    """
    import sqlite3

    logger.info("📊 Available Databases in data/")
    logger.info("="*70 + "\n")

    data_dir = Path('data')

    if not data_dir.exists():
        logger.warning("⚠️  No data directory found")
        logger.info("   Create the data/ directory and add database files")
        return

    db_files = list(data_dir.rglob('*.db'))

    if not db_files:
        logger.warning("⚠️  No database files found in data/")
        logger.info("   Add .db files to the data/ directory")
        logger.info("\n   Example: Import Alibaba data with:")
        logger.info("   text2sql2chart data import-alibaba --day-dir data/alibaba2018/day_1")
        return

    logger.info(f"Found {len(db_files)} database(s):\n")

    for db_path in sorted(db_files):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()

            # Get total rows
            total_rows = 0
            table_details = []
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                count = cursor.fetchone()[0]
                total_rows += count
                table_details.append(f"{table[0]} ({count:,} rows)")

            logger.info(f"📁 {db_path}")
            logger.info(f"   Tables: {len(tables)}")
            logger.info(f"   Total rows: {total_rows:,}")
            if table_details:
                logger.info(f"   Details: {', '.join(table_details)}")
            logger.info("")

            conn.close()

        except Exception as e:
            logger.warning(f"📁 {db_path}")
            logger.warning(f"   ⚠️  Error reading database: {e}")
            logger.info("")

    logger.info("="*70)
