"""
Grafana Automation Module

Automates complete Grafana setup:
- Docker service orchestration
- Datasource configuration
- Dashboard import
- Health monitoring
"""

import subprocess
import time
import json
import sys
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict
from dataclasses import dataclass

try:
    import requests
except ImportError:
    print("Installing requests library...")
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    import requests

from .config import GrafanaConfig, get_default_config
from .models import (
    AutomationResult,
    DatasourceConfig,
    ServiceHealth,
    ServiceStatus
)

logger = logging.getLogger(__name__)


class GrafanaAutomation:
    """
    Complete Grafana automation workflow

    Handles:
    - Prerequisites checking
    - Docker service management
    - Datasource configuration
    - Dashboard import
    - Health monitoring
    """

    def __init__(self, config: Optional[GrafanaConfig] = None):
        """
        Initialize automation

        Args:
            config: GrafanaConfig instance (uses defaults if not provided)
        """
        self.config = config or get_default_config()
        self.result = AutomationResult(success=True)

    def run(self, open_browser: bool = True) -> AutomationResult:
        """
        Execute complete automation workflow

        Args:
            open_browser: Whether to open browser to dashboard

        Returns:
            AutomationResult with status and details
        """
        try:
            logger.info("=" * 70)
            logger.info("  GRAFANA AUTOMATION - ZERO MANUAL STEPS")
            logger.info("=" * 70)

            # Step 1: Check prerequisites
            if not self.check_prerequisites():
                return self.result

            # Step 2: Stop existing services
            self.stop_existing_services()

            # Step 3: Start services
            if not self.start_services():
                return self.result

            # Step 4: Wait for services
            if not self.wait_for_services():
                return self.result

            # Step 5: Configure datasource
            datasource_uid = self.configure_datasource()
            if datasource_uid:
                self.result.datasource_uid = datasource_uid
            else:
                self.result.add_warning("Datasource configuration had issues")

            # Step 6: Import dashboard
            dashboard_result = self.import_dashboard()
            if dashboard_result:
                dashboard_uid, dashboard_url = dashboard_result
                self.result.dashboard_url = f"{self.config.grafana_url}{dashboard_url}"
            else:
                self.result.add_error("Dashboard import failed")
                return self.result

            # Step 7: Open browser
            if open_browser and dashboard_url:
                self.open_browser(dashboard_url)

            logger.info("=" * 70)
            logger.info("  ✅ AUTOMATION COMPLETE!")
            logger.info("=" * 70)

            return self.result

        except KeyboardInterrupt:
            logger.warning("\n⚠ Interrupted by user")
            self.result.add_error("Interrupted by user")
            return self.result

        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}", exc_info=True)
            self.result.add_error(f"Unexpected error: {e}")
            return self.result

    def check_prerequisites(self) -> bool:
        """Check required files and services exist"""
        logger.info("\n[STEP 1] Checking Prerequisites")
        logger.info("-" * 70)

        # Required files
        required_files = [
            self.config.docker_compose_file,
            Path("docker/api/Dockerfile"),
            self.config.dashboard_file,
            self.config.data_dir / "chart_1_data.json"
        ]

        missing = []
        for f in required_files:
            if not f.exists():
                missing.append(str(f))
                logger.error(f"  ✗ Missing: {f}")
            else:
                logger.info(f"  ✓ Found: {f}")

        if missing:
            self.result.add_error(f"Missing required files: {missing}")
            logger.error("\n❌ Missing files. Run: python examples/demo_grafana.py quick")
            return False

        # Check Docker
        try:
            result = subprocess.run(
                ["docker", "ps"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info("  ✓ Docker is running")
                self.result.services['docker'] = ServiceHealth(
                    service_name='docker',
                    status=ServiceStatus.RUNNING,
                    url='N/A'
                )
            else:
                logger.error("  ✗ Docker is not running")
                self.result.add_error("Docker is not running")
                return False
        except Exception as e:
            logger.error(f"  ✗ Docker not found: {e}")
            self.result.add_error("Docker not found")
            return False

        logger.info("\n✅ All prerequisites met!")
        return True

    def stop_existing_services(self):
        """Stop any existing Docker containers"""
        logger.info("\n[STEP 2] Stopping Existing Services")
        logger.info("-" * 70)

        try:
            subprocess.run(
                ["docker-compose", "down"],
                capture_output=True,
                timeout=30
            )
            logger.info("  ✓ Cleanup complete")
        except Exception as e:
            logger.warning(f"  ⚠ Cleanup error (non-fatal): {e}")

    def start_services(self) -> bool:
        """Start Docker services"""
        logger.info("\n[STEP 3] Starting Docker Services")
        logger.info("-" * 70)

        try:
            result = subprocess.run(
                ["docker-compose", "up", "-d", "--build"],
                capture_output=True,
                text=True,
                timeout=180
            )

            if result.returncode != 0:
                logger.error("  ✗ Failed to start services")
                logger.error(result.stderr)
                self.result.add_error(f"Docker start failed: {result.stderr}")
                return False

            logger.info("  ✓ Containers started!")
            return True

        except subprocess.TimeoutExpired:
            logger.error("  ✗ Docker start timeout")
            self.result.add_error("Docker start timeout")
            return False
        except Exception as e:
            logger.error(f"  ✗ Error starting services: {e}")
            self.result.add_error(f"Service start error: {e}")
            return False

    def wait_for_services(self) -> bool:
        """Wait for services to be ready"""
        logger.info("\n[STEP 4] Waiting for Services")
        logger.info("-" * 70)

        # Wait for API server
        logger.info("  Waiting for API server (port 5000)...")
        api_ready = self._wait_for_service(
            url="http://localhost:5000/",
            service_name="api-server",
            max_attempts=30,
            timeout_per_attempt=2
        )

        if not api_ready:
            logger.error("  ✗ API server failed to start")
            self.result.add_error("API server startup failed")
            return False

        logger.info("  ✓ API server ready!")

        # Wait for Grafana
        logger.info("  Waiting for Grafana (port 3000)...")
        grafana_ready = self._wait_for_service(
            url=f"{self.config.grafana_url}/api/health",
            service_name="grafana",
            max_attempts=60,
            timeout_per_attempt=2
        )

        if not grafana_ready:
            logger.error("  ✗ Grafana failed to start")
            self.result.add_error("Grafana startup failed")
            return False

        logger.info("  ✓ Grafana ready!")
        logger.info("  ⏳ Waiting 5s for full initialization...")
        time.sleep(5)

        logger.info("\n✅ All services ready!")
        return True

    def _wait_for_service(
        self,
        url: str,
        service_name: str,
        max_attempts: int,
        timeout_per_attempt: int
    ) -> bool:
        """
        Wait for a service to become ready

        Args:
            url: Service health check URL
            service_name: Service name for logging
            max_attempts: Maximum number of attempts
            timeout_per_attempt: Timeout for each attempt (seconds)

        Returns:
            True if service is ready, False otherwise
        """
        for i in range(max_attempts):
            try:
                response = requests.get(url, timeout=timeout_per_attempt)
                if response.status_code == 200:
                    self.result.services[service_name] = ServiceHealth(
                        service_name=service_name,
                        status=ServiceStatus.RUNNING,
                        url=url,
                        message="Service is healthy"
                    )
                    return True
            except requests.RequestException:
                pass

            if i % 5 == 0 and i > 0:
                print(".", end="", flush=True)
            time.sleep(1)

        print()  # New line after dots
        self.result.services[service_name] = ServiceHealth(
            service_name=service_name,
            status=ServiceStatus.ERROR,
            url=url,
            message="Service failed to start"
        )
        return False

    def configure_datasource(self) -> Optional[str]:
        """
        Auto-configure JSON datasource in Grafana

        Returns:
            Datasource UID if successful, None otherwise
        """
        logger.info("\n[STEP 5] Configuring Datasource")
        logger.info("-" * 70)

        datasource_config = DatasourceConfig(
            name=self.config.datasource_name,
            type=self.config.datasource_type,
            url=self.config.api_url_internal,
        )

        try:
            # Check if datasource already exists
            response = requests.get(
                f"{self.config.grafana_url}/api/datasources/name/{self.config.datasource_name.replace(' ', '%20')}",
                auth=(self.config.grafana_user, self.config.grafana_password),
                timeout=self.config.api_timeout
            )

            if response.status_code == 200:
                logger.info("  ℹ Datasource exists, updating...")
                datasource_id = response.json()['id']
                response = requests.put(
                    f"{self.config.grafana_url}/api/datasources/{datasource_id}",
                    json=datasource_config.to_dict(),
                    auth=(self.config.grafana_user, self.config.grafana_password),
                    timeout=self.config.api_timeout
                )
            else:
                logger.info("  Creating new datasource...")
                response = requests.post(
                    f"{self.config.grafana_url}/api/datasources",
                    json=datasource_config.to_dict(),
                    auth=(self.config.grafana_user, self.config.grafana_password),
                    timeout=self.config.api_timeout
                )

            if response.status_code in [200, 201]:
                logger.info("  ✓ Datasource configured!")
                result = response.json()
                datasource_uid = result.get('datasource', {}).get('uid') or result.get('uid')
                logger.info(f"  Datasource UID: {datasource_uid}")
                return datasource_uid
            else:
                logger.warning(f"  ⚠ Datasource response: {response.status_code}")
                logger.warning(f"  Response: {response.text}")
                self.result.add_warning(f"Datasource config issue: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"  ✗ Error configuring datasource: {e}")
            self.result.add_error(f"Datasource configuration error: {e}")
            return None

    def import_dashboard(self) -> Optional[Tuple[str, str]]:
        """
        Auto-import dashboard to Grafana

        Returns:
            Tuple of (dashboard_uid, dashboard_url) if successful, None otherwise
        """
        logger.info("\n[STEP 6] Importing Dashboard")
        logger.info("-" * 70)

        if not self.config.dashboard_file.exists():
            logger.error(f"  ✗ Dashboard file not found: {self.config.dashboard_file}")
            self.result.add_error("Dashboard file not found")
            return None

        try:
            with open(self.config.dashboard_file, 'r') as f:
                dashboard_json = json.load(f)

            logger.info(f"  Loaded: {self.config.dashboard_file.name}")

            # Get datasource UID
            ds_response = requests.get(
                f"{self.config.grafana_url}/api/datasources/name/{self.config.datasource_name.replace(' ', '%20')}",
                auth=(self.config.grafana_user, self.config.grafana_password),
                timeout=self.config.api_timeout
            )

            datasource_uid = None
            if ds_response.status_code == 200:
                datasource_uid = ds_response.json().get('uid')
                logger.info(f"  Datasource UID: {datasource_uid}")

            # Update panel datasources
            if 'dashboard' in dashboard_json and datasource_uid:
                for panel in dashboard_json['dashboard'].get('panels', []):
                    if 'datasource' in panel:
                        panel['datasource'] = {
                            "type": self.config.datasource_type,
                            "uid": datasource_uid
                        }
                    for target in panel.get('targets', []):
                        if 'datasource' in target:
                            target['datasource'] = {
                                "type": self.config.datasource_type,
                                "uid": datasource_uid
                            }

            # Import dashboard
            logger.info("  Importing to Grafana...")
            response = requests.post(
                f"{self.config.grafana_url}/api/dashboards/db",
                json=dashboard_json,
                auth=(self.config.grafana_user, self.config.grafana_password),
                timeout=self.config.api_timeout
            )

            if response.status_code == 200:
                result = response.json()
                dashboard_uid = result.get('uid')
                dashboard_url = result.get('url')

                logger.info("  ✓ Dashboard imported!")
                logger.info(f"  UID: {dashboard_uid}")
                logger.info(f"  URL: {self.config.grafana_url}{dashboard_url}")

                return dashboard_uid, dashboard_url
            else:
                logger.warning(f"  ⚠ Dashboard response: {response.status_code}")
                logger.warning(f"  Response: {response.text}")
                self.result.add_error(f"Dashboard import failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"  ✗ Error importing dashboard: {e}", exc_info=True)
            self.result.add_error(f"Dashboard import error: {e}")
            return None

    def open_browser(self, dashboard_url: Optional[str] = None):
        """
        Open browser to dashboard

        Args:
            dashboard_url: Relative dashboard URL (e.g., /d/xxx/dashboard-name)
        """
        logger.info("\n[STEP 7] Opening Browser")
        logger.info("-" * 70)

        url = f"{self.config.grafana_url}{dashboard_url}" if dashboard_url else self.config.grafana_url
        logger.info(f"  Opening: {url}")

        try:
            if sys.platform == 'darwin':  # macOS
                subprocess.run(["open", url])
            elif sys.platform == 'win32':  # Windows
                subprocess.run(["start", url], shell=True)
            else:  # Linux/WSL
                try:
                    subprocess.run(["xdg-open", url], capture_output=True, timeout=5)
                except:
                    try:
                        # WSL - use Windows browser
                        subprocess.run(
                            ["/mnt/c/Windows/System32/cmd.exe", "/c", "start", url],
                            capture_output=True,
                            timeout=5
                        )
                    except:
                        pass

            logger.info("  ✓ Browser opened")
        except Exception as e:
            logger.info(f"  ℹ Could not auto-open browser: {e}")

    def print_summary(self):
        """Print completion summary"""
        logger.info("\n" + "=" * 70)
        logger.info("  ✅ SETUP COMPLETE!")
        logger.info("=" * 70)

        if self.result.success:
            print(f"""
🎉 Everything is ready!

🌐 Dashboard: {self.result.dashboard_url or self.config.grafana_url}
   Username: {self.config.grafana_user}
   Password: (see GRAFANA_PASSWORD)

📊 Services:""")
            for name, health in self.result.services.items():
                status_icon = "✅" if health.is_healthy() else "❌"
                print(f"   {status_icon} {name}: {health.status.value}")

            print(f"""
🛑 Stop: docker-compose down
🔄 Restart: python -m text2sql2chart.cli grafana run
""")
        else:
            print("\n❌ Setup completed with errors:")
            for error in self.result.errors:
                print(f"  • {error}")
