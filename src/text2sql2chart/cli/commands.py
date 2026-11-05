"""
Main CLI Entry Point

Provides command-line interface for text2sql2chart operations.
"""

import argparse
import logging
import sys
from pathlib import Path

from .data_cli import data_command


def setup_logging(level: str = "INFO", debug: bool = False):
    """
    Configure logging for the application

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        debug: Enable debug mode
    """
    if debug:
        level = "DEBUG"

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        prog='text2sql2chart',
        description='Text-to-SQL-to-Chart: AI-powered database analysis and visualization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start the API server
  text2sql2chart serve --host 0.0.0.0 --port 5000

  # Import Alibaba cluster data
  text2sql2chart data import-alibaba --day-dir data/alibaba2018/day_1

  # List available databases
  text2sql2chart data list

  # Verify database structure
  text2sql2chart data verify --database data/alibaba2018/alibaba_cluster.db

For more information, visit: https://github.com/yourusername/text2sql2chart
        """
    )

    # Global arguments
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.0.0'
    )
    parser.add_argument(
        '--config',
        type=Path,
        help='Path to configuration file'
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Set logging level (default: INFO)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )

    # Subcommands
    subparsers = parser.add_subparsers(
        title='commands',
        description='Available commands',
        dest='command',
        help='Command to execute'
    )

    # Serve command - Start API server
    serve_parser = subparsers.add_parser(
        'serve',
        help='Start the API server',
        description='Run the visualization API server (endpoints: /visualize, /search, /query)'
    )
    serve_parser.add_argument(
        '--host',
        default=None,
        help='Host to bind to (default: from config or 0.0.0.0)'
    )
    serve_parser.add_argument(
        '--port',
        type=int,
        default=None,
        help='Port to bind to (default: from config or 5000)'
    )
    serve_parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable Flask debug mode'
    )
    serve_parser.set_defaults(func=cmd_serve)

    # Data command
    data_parser = subparsers.add_parser(
        'data',
        help='Data import and management',
        description='Import and manage data sources'
    )
    data_command(data_parser)

    # Parse arguments
    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level, args.debug)

    # Execute command
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Dispatch to command handler
    if hasattr(args, 'func'):
        try:
            args.func(args)
        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            sys.exit(130)
        except Exception as e:
            logging.error(f"Error: {e}", exc_info=args.debug)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


logger = logging.getLogger(__name__)


def cmd_serve(args):
    """Start the visualization API server"""
    from ..grafana.api_server import run_api_server
    from ..grafana.config import load_config

    logger.info("Starting API server")

    config = load_config(getattr(args, 'config', None))

    try:
        run_api_server(
            config=config,
            host=args.host,
            port=args.port,
            debug=args.debug
        )
    except KeyboardInterrupt:
        logger.info("\nShutting down API server...")
        sys.exit(0)


if __name__ == '__main__':
    main()
