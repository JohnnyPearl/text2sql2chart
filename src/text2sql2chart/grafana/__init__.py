"""
Grafana Integration Module

This module provides complete Grafana integration including:
- API server for serving chart data
- Automated dashboard deployment
- Configuration management
- Docker orchestration
"""

from .config import GrafanaConfig, get_default_config
from .automation import GrafanaAutomation
from .api_server import create_app, run_api_server

__all__ = [
    'GrafanaConfig',
    'get_default_config',
    'GrafanaAutomation',
    'create_app',
    'run_api_server',
]

__version__ = '1.0.0'
