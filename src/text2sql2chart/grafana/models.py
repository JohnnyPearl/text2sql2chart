"""
Data Models for Grafana Integration

Defines data structures for Grafana datasources, dashboards, and chart data.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class ServiceStatus(Enum):
    """Service health status"""
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class DataPoint:
    """Represents a single data point in Grafana format"""
    value: float
    index: int

    def to_list(self) -> List[float]:
        """Convert to Grafana format: [value, index]"""
        return [self.value, self.index]


@dataclass
class TimeSeries:
    """Represents a time series for Grafana"""
    target: str
    datapoints: List[List[float]]  # [[value, timestamp/index], ...]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Grafana JSON format"""
        return {
            "target": self.target,
            "datapoints": self.datapoints
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TimeSeries':
        """Create from dictionary"""
        return cls(
            target=data.get('target', ''),
            datapoints=data.get('datapoints', [])
        )


@dataclass
class DatasourceConfig:
    """Grafana datasource configuration"""
    name: str
    type: str
    url: str
    access: str = "proxy"
    is_default: bool = True
    json_data: Dict[str, Any] = field(default_factory=lambda: {"tlsSkipVerify": True})
    uid: Optional[str] = None
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Grafana API format"""
        data = {
            "name": self.name,
            "type": self.type,
            "url": self.url,
            "access": self.access,
            "isDefault": self.is_default,
            "jsonData": self.json_data
        }
        if self.uid:
            data["uid"] = self.uid
        if self.id:
            data["id"] = self.id
        return data


@dataclass
class DashboardPanel:
    """Grafana dashboard panel configuration"""
    id: int
    title: str
    type: str
    targets: List[Dict[str, Any]]
    grid_pos: Dict[str, int]
    datasource: Optional[Dict[str, str]] = None
    options: Dict[str, Any] = field(default_factory=dict)
    field_config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Grafana format"""
        data = {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "targets": self.targets,
            "gridPos": self.grid_pos,
        }
        if self.datasource:
            data["datasource"] = self.datasource
        if self.options:
            data["options"] = self.options
        if self.field_config:
            data["fieldConfig"] = self.field_config
        return data


@dataclass
class Dashboard:
    """Grafana dashboard"""
    title: str
    uid: str
    panels: List[DashboardPanel]
    tags: List[str] = field(default_factory=list)
    timezone: str = "browser"
    schema_version: int = 38
    version: int = 1
    refresh: str = "5m"
    editable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Grafana API format"""
        return {
            "dashboard": {
                "title": self.title,
                "uid": self.uid,
                "tags": self.tags,
                "timezone": self.timezone,
                "schemaVersion": self.schema_version,
                "version": self.version,
                "refresh": self.refresh,
                "editable": self.editable,
                "panels": [panel.to_dict() for panel in self.panels],
                "time": {
                    "from": "now-6h",
                    "to": "now"
                },
                "graphTooltip": 1,
                "links": []
            },
            "overwrite": True
        }


@dataclass
class ServiceHealth:
    """Service health check result"""
    service_name: str
    status: ServiceStatus
    url: str
    message: Optional[str] = None
    response_time_ms: Optional[float] = None

    def is_healthy(self) -> bool:
        """Check if service is healthy"""
        return self.status == ServiceStatus.RUNNING

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "service_name": self.service_name,
            "status": self.status.value,
            "url": self.url,
            "message": self.message,
            "response_time_ms": self.response_time_ms,
            "healthy": self.is_healthy()
        }


@dataclass
class AutomationResult:
    """Result of automation process"""
    success: bool
    dashboard_url: Optional[str] = None
    datasource_uid: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    services: Dict[str, ServiceHealth] = field(default_factory=dict)

    def add_error(self, error: str):
        """Add an error message"""
        self.errors.append(error)
        self.success = False

    def add_warning(self, warning: str):
        """Add a warning message"""
        self.warnings.append(warning)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "dashboard_url": self.dashboard_url,
            "datasource_uid": self.datasource_uid,
            "errors": self.errors,
            "warnings": self.warnings,
            "services": {
                name: health.to_dict()
                for name, health in self.services.items()
            }
        }
