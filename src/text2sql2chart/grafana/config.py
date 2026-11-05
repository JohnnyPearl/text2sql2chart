"""
Configuration Management for Grafana Integration

Handles configuration with the following priority:
1. Environment variables (highest)
2. Config file
3. Defaults (lowest)
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class GrafanaConfig:
    """Grafana configuration settings"""

    # Grafana settings
    grafana_url: str = field(default="http://localhost:3000")
    grafana_user: str = field(default="")
    grafana_password: str = field(default="")

    # API server settings
    api_host: str = field(default="0.0.0.0")
    api_port: int = field(default=5000)
    api_url_internal: str = field(default="http://api-server:5000")  # For Docker network
    api_url_external: str = field(default="http://localhost:5000")   # For host access

    # Data paths
    data_dir: Path = field(default_factory=lambda: Path("generate_output/grafana/data"))
    dashboard_file: Path = field(default_factory=lambda: Path("generate_output/grafana/grafana_dashboard.json"))
    output_dir: Path = field(default_factory=lambda: Path("generate_output"))

    # Docker settings
    docker_compose_file: Path = field(default_factory=lambda: Path("docker-compose.yml"))

    # Datasource settings
    datasource_name: str = field(default="JSON API")
    datasource_type: str = field(default="simpod-json-datasource")

    # Timeouts
    service_startup_timeout: int = field(default=60)  # seconds
    api_timeout: int = field(default=10)  # seconds

    # TimescaleDB connection
    timescaledb_host: str = field(default="localhost")
    timescaledb_port: int = field(default=5432)
    timescaledb_db: str = field(default="")
    timescaledb_user: str = field(default="")
    timescaledb_password: str = field(default="")

    # InfluxDB connection
    influxdb_url: str = field(default="http://localhost:8086")
    influxdb_token: str = field(default="")
    influxdb_org: str = field(default="")
    influxdb_bucket: str = field(default="")

    # Logging
    log_level: str = field(default="INFO")
    debug: bool = field(default=False)

    def __post_init__(self):
        """Convert string paths to Path objects"""
        if isinstance(self.data_dir, str):
            self.data_dir = Path(self.data_dir)
        if isinstance(self.dashboard_file, str):
            self.dashboard_file = Path(self.dashboard_file)
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)
        if isinstance(self.docker_compose_file, str):
            self.docker_compose_file = Path(self.docker_compose_file)

    @classmethod
    def from_env(cls) -> 'GrafanaConfig':
        """Create configuration from environment variables"""
        return cls(
            grafana_url=os.getenv('GRAFANA_URL', 'http://localhost:3000'),
            grafana_user=os.getenv('GRAFANA_USER', ''),
            grafana_password=os.getenv('GRAFANA_PASSWORD', ''),
            api_host=os.getenv('API_HOST', '0.0.0.0'),
            api_port=int(os.getenv('API_PORT', '5000')),
            api_url_internal=os.getenv('API_URL_INTERNAL', 'http://api-server:5000'),
            api_url_external=os.getenv('API_URL_EXTERNAL', 'http://localhost:5000'),
            data_dir=Path(os.getenv('DATA_DIR', 'generate_output/grafana/data')),
            dashboard_file=Path(os.getenv('DASHBOARD_FILE', 'generate_output/grafana/grafana_dashboard.json')),
            output_dir=Path(os.getenv('OUTPUT_DIR', 'generate_output')),
            timescaledb_host=os.getenv('TIMESCALEDB_HOST', 'localhost'),
            timescaledb_port=int(os.getenv('TIMESCALEDB_PORT', '5432')),
            timescaledb_db=os.getenv('TIMESCALEDB_DB', ''),
            timescaledb_user=os.getenv('TIMESCALEDB_USER', ''),
            timescaledb_password=os.getenv('TIMESCALEDB_PASSWORD', ''),
            influxdb_url=os.getenv('INFLUXDB_URL', 'http://localhost:8086'),
            influxdb_token=os.getenv('INFLUXDB_TOKEN', ''),
            influxdb_org=os.getenv('INFLUXDB_ORG', ''),
            influxdb_bucket=os.getenv('INFLUXDB_BUCKET', ''),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            debug=os.getenv('DEBUG', 'false').lower() == 'true',
        )

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate configuration

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Validate paths exist when needed
        if not self.data_dir.exists():
            errors.append(f"Data directory not found: {self.data_dir}")

        if not self.dashboard_file.exists():
            errors.append(f"Dashboard file not found: {self.dashboard_file}")

        # Validate ports
        if not (1024 <= self.api_port <= 65535):
            errors.append(f"Invalid API port: {self.api_port} (must be 1024-65535)")

        # Validate URLs
        if not self.grafana_url.startswith(('http://', 'https://')):
            errors.append(f"Invalid Grafana URL: {self.grafana_url}")

        return len(errors) == 0, errors

    def to_dict(self) -> dict:
        """Convert config to dictionary"""
        return {
            'grafana_url': self.grafana_url,
            'grafana_user': self.grafana_user,
            'api_host': self.api_host,
            'api_port': self.api_port,
            'api_url_internal': self.api_url_internal,
            'api_url_external': self.api_url_external,
            'data_dir': str(self.data_dir),
            'dashboard_file': str(self.dashboard_file),
            'output_dir': str(self.output_dir),
            'datasource_name': self.datasource_name,
            'datasource_type': self.datasource_type,
            'log_level': self.log_level,
            'debug': self.debug,
        }


def get_default_config() -> GrafanaConfig:
    """Get default configuration with environment overrides"""
    return GrafanaConfig.from_env()


def load_config(config_file: Optional[Path] = None) -> GrafanaConfig:
    """
    Load configuration from file with environment overrides

    Args:
        config_file: Path to YAML config file (optional)

    Returns:
        GrafanaConfig instance
    """
    # Start with defaults
    config = GrafanaConfig()

    # TODO: Add YAML config file support if needed
    if config_file and config_file.exists():
        logger.info(f"Loading config from {config_file}")
        # Could add YAML parsing here

    # Override with environment variables
    env_config = GrafanaConfig.from_env()

    # Merge (env vars take precedence)
    for key in config.__dataclass_fields__.keys():
        env_value = getattr(env_config, key)
        default_value = getattr(GrafanaConfig(), key)
        if env_value != default_value:
            setattr(config, key, env_value)
            logger.debug(f"Config override from env: {key}={env_value}")

    return config
