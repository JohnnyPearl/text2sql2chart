"""
Demo: Grafana Integration with Vanna Data Analysis

This demo shows how to:
1. Extract data from database using Vanna
2. Create visualizations with Plotly
3. Generate Grafana dashboards automatically
4. Export data in multiple formats

Usage:
    python demo_grafana.py
"""

import os

# Disable browser auto-opening in headless/WSL environments
os.environ['BROWSER'] = 'echo'

# Disable Plotly browser rendering
import plotly.io as pio
pio.renderers.default = 'json'

from vanna.openai import OpenAI_Chat
from vanna.chromadb import ChromaDB_VectorStore
from text2sql2chart.multi_chart_analysis_agent import create_multi_chart_agent
from text2sql2chart.grafana_generator import convert_chart_results_to_grafana


def demo_grafana_integration(user_request=None, output_dir=None, api_key=None):
    """
    Complete demo of Grafana integration

    Args:
        user_request: Custom analysis prompt (default: "Please analyze and create smart charts for this database")
        output_dir: Output directory for results (default: 'demo_grafana_output')
        api_key: OpenAI API key (default: read from the OPENAI_API_KEY environment variable)
    """

    print("="*80)
    print("GRAFANA INTEGRATION DEMO")
    print("="*80)

    # ============================================================================
    # STEP 1: Setup Vanna and Agent
    # ============================================================================
    print("\n[STEP 1] Setting up Vanna and Analysis Agent...")

    # API key: use provided key or fall back to environment variable
    if api_key is None:
        API_KEY = os.getenv('OPENAI_API_KEY')
        if not API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable not set.")
    else:
        API_KEY = api_key

    class MyVanna(ChromaDB_VectorStore, OpenAI_Chat):
        def __init__(self, config=None):
            ChromaDB_VectorStore.__init__(self, config=config)
            OpenAI_Chat.__init__(self, config=config)

    vn = MyVanna(config={
        'api_key': API_KEY,
        'model': 'gpt-4o-mini'
    })

    # Connect to your database
    database_path = 'data/sql-murder-mystery.db'
    vn.connect_to_sqlite(database_path)

    # Create analysis agent
    agent = create_multi_chart_agent(vn, API_KEY)

    print("✓ Setup complete!")

    # ============================================================================
    # STEP 2: Analyze Data and Create Charts
    # ============================================================================
    print("\n[STEP 2] Analyzing data and creating charts...")

    # Set default user request if not provided
    if user_request is None:
        user_request = "Please analyze and create smart charts for this database"

    # Set default output directories if not provided
    if output_dir is None:
        output_dir = 'demo_grafana_output'
        output_dir_integrated = 'demo_grafana_integrated'
    else:
        output_dir_integrated = f'{output_dir}_integrated'

    print(f"User request: {user_request}")
    print(f"Output directory: {output_dir}")

    result = agent.analyze(
        user_request=user_request,
        max_charts=5,
        analysis_mode='smart',
        dashboard_theme='modern'
    )

    if not result.get('success'):
        print("❌ Analysis failed!")
        return

    print(f"✓ Analysis complete!")
    print(f"  Created {result['summary']['successful_charts']} charts")

    # ============================================================================
    # STEP 3: Generate Grafana Dashboard (Method 1: Using convenience function)
    # ============================================================================
    print("\n[STEP 3] Generating Grafana dashboard...")

    chart_results = result.get('chart_results', {})
    successful_charts = chart_results.get('successful_charts', [])

    if successful_charts:
        # Method 1: Use convenience function
        grafana_info = convert_chart_results_to_grafana(
            chart_results=successful_charts,
            title="Data Analysis Dashboard",
            datasource_type='json',  # Options: 'json', 'csv', 'sqlite'
            database_path=database_path,
            output_dir=output_dir
        )

        print("\n✓ Grafana dashboard generated!")

    # ============================================================================
    # STEP 4: Alternative - Save with integrated method
    # ============================================================================
    print("\n[STEP 4] Alternative: Using integrated save method...")

    agent.save_results_with_grafana(
        results=result,
        output_dir=output_dir_integrated,
        grafana_datasource='json',
        database_path=database_path
    )

    print("\n✓ All files saved!")

    # ============================================================================
    # SUMMARY
    # ============================================================================
    print("\n" + "="*80)
    print("DEMO COMPLETE!")
    print("="*80)
    print("\nGenerated Files:")
    print("  Method 1 (Standalone):")
    print(f"    - {output_dir}/grafana_dashboard.json")
    print(f"    - {output_dir}/data/*.csv")
    print(f"    - {output_dir}/data/*.json")
    print(f"    - {output_dir}/datasource_config.json")
    print()
    print("  Method 2 (Integrated):")
    print(f"    - {output_dir_integrated}/grafana/grafana_dashboard.json")
    print(f"    - {output_dir_integrated}/grafana/data/*.csv")
    print(f"    - {output_dir_integrated}/grafana/data/*.json")
    print(f"    - {output_dir_integrated}/main_dashboard.html (Plotly)")
    print()
    print("Next Steps:")
    print("1. Install Grafana:")
    print("   - Download: https://grafana.com/grafana/download")
    print("   - Or Docker: docker run -d -p 3000:3000 grafana/grafana")
    print()
    print("2. Import Dashboard:")
    print("   - Open Grafana (http://localhost:3000)")
    print("   - Go to Dashboards → Import")
    print(f"   - Upload: {output_dir}/grafana_dashboard.json")
    print()
    print("3. Configure Datasource:")
    print("   - Go to Configuration → Data Sources")
    print("   - Add data source based on datasource_config.json")
    print("   - For JSON: Install 'JSON API' plugin")
    print("   - For CSV: Install 'CSV datasource' plugin")
    print("   - For SQLite: Install 'SQLite datasource' plugin")
    print()
    print("4. View Your Data!")
    print("="*80)


def demo_quick_grafana(user_request=None, output_dir=None, api_key=None, max_charts=3,
                       database_path=None, provider="openai"):
    """
    Quick demo with minimal code - Generates fresh data every time

    Args:
        user_request: Custom analysis prompt (default: "Please analyze and create smart charts for this database")
        output_dir: Output directory for results (default: 'generate_output')
        api_key: API key for the AI provider
        max_charts: Number of charts to generate (default: 3)
        database_path: Path to SQLite database (default: data/sql-murder-mystery.db or DATABASE_PATH env var)
        provider: AI provider to use: 'openai' or 'gemini' (default: 'openai')
    """
    from datetime import datetime
    import os

    print("="*80)
    print("QUICK GRAFANA DEMO - FRESH DATA GENERATION")
    print("="*80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"AI Provider: {provider.upper()}")
    print()

    # API key: use provided key or fall back to environment variable
    if api_key is None:
        if provider == "gemini":
            API_KEY = os.getenv('GEMINI_API_KEY')
        else:
            API_KEY = os.getenv('OPENAI_API_KEY')
        if not API_KEY:
            env_var = 'GEMINI_API_KEY' if provider == 'gemini' else 'OPENAI_API_KEY'
            raise ValueError(f"{env_var} environment variable not set.")
    else:
        API_KEY = api_key

    # Database path configuration: CLI arg > Environment variable > Default
    if database_path is None:
        DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/sql-murder-mystery.db')
    else:
        DATABASE_PATH = database_path

    print("[1/4] Initializing Vanna and Analysis Agent...")
    print(f"Database: {DATABASE_PATH}")

    from vanna.chromadb import ChromaDB_VectorStore

    if provider == "gemini":
        from vanna.google.gemini_chat import GoogleGeminiChat

        class MyVanna(ChromaDB_VectorStore, GoogleGeminiChat):
            def __init__(self, config=None):
                ChromaDB_VectorStore.__init__(self, config=config)
                GoogleGeminiChat.__init__(self, config=config)

        vn = MyVanna(config={'api_key': API_KEY, 'model_name': 'gemini-2.0-flash'})
    else:
        from vanna.openai import OpenAI_Chat

        class MyVanna(ChromaDB_VectorStore, OpenAI_Chat):
            def __init__(self, config=None):
                ChromaDB_VectorStore.__init__(self, config=config)
                OpenAI_Chat.__init__(self, config=config)

        vn = MyVanna(config={'api_key': API_KEY, 'model': 'gpt-4o-mini'})

    vn.connect_to_sqlite(DATABASE_PATH)

    # Auto-detect Alibaba database and train schema
    if 'alibaba' in DATABASE_PATH.lower():
        print("  Detected Alibaba database - training schema...")
        try:
            from text2sql2chart.data_import import train_vanna_alibaba_schema
            train_vanna_alibaba_schema(vn, DATABASE_PATH)
        except Exception as e:
            print(f"  ⚠️  Warning: Could not train Alibaba schema: {e}")

    agent = create_multi_chart_agent(vn, API_KEY, provider=provider)
    print("✓ Initialization complete\n")

    # Set defaults for user_request and output_dir
    if user_request is None:
        user_request = "Please analyze and create smart charts for this database"

    if output_dir is None:
        # output_dir = 'quick_grafana_output'
        output_dir = 'generate_output'

    print(f"User request: {user_request}")
    print(f"Output directory: {output_dir}")
    print(f"Max charts: {max_charts}\n")

    # Analyze
    print("[2/4] Analyzing database and generating SQL queries...")
    result = agent.analyze(user_request, max_charts=max_charts)

    if not result.get('success'):
        print("❌ Analysis failed!")
        return

    chart_count = result['summary']['successful_charts']
    print(f"✓ Analysis complete - Generated {chart_count} charts\n")

    # Generate Grafana dashboard
    print("[3/4] Creating Grafana dashboard and exporting data...")
    if result.get('success'):
        agent.save_results_with_grafana(
            results=result,
            output_dir=output_dir,
            grafana_datasource='json',
            database_path=DATABASE_PATH
        )

    print("[4/4] Finalizing...")
    print("\n" + "="*80)
    print("✓ DEMO COMPLETE - Fresh Data Generated!")
    print("="*80)
    print(f"Output Directory: {output_dir}/grafana/")
    print(f"Data Files: {output_dir}/grafana/data/")
    print(f"Dashboard: {output_dir}/grafana/grafana_dashboard.json")
    print(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)


if __name__ == "__main__":
    import sys

    print("\n")
    print("="*80)
    print("GRAFANA INTEGRATION DEMO")
    print("="*80)
    print("\nAvailable demos:")
    print("  1. Full demo (demo_grafana_integration)")
    print("  2. Quick demo (demo_quick_grafana)")
    print()

    if len(sys.argv) > 1:
        if sys.argv[1] == 'quick':
            demo_quick_grafana()
        else:
            demo_grafana_integration()
    else:
        print("Usage:")
        print("  python demo_grafana.py          # Run full demo")
        print("  python demo_grafana.py quick    # Run quick demo")
        print()
        print("NOTE: Update API_KEY in the script before running!")
