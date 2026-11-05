import os
from pathlib import Path
from typing import Dict, List, Any


class DashboardGenerator:
    """Create simple dashboard by stacking chart HTML from top to bottom"""
    
    def __init__(self):
        pass
    
    def create_dashboard(self,
                        chart_results: List[Dict[str, Any]],
                        title: str = "Data Analysis Dashboard",
                        theme: str = 'modern',
                        layout_style: str = 'auto',
                        output_dir: str = None) -> str:
        """Create simple dashboard by stacking chart HTML already created from top to bottom"""
        
        successful_charts = [r for r in chart_results if r.get('success', False)]
        
        if not successful_charts:
            return self._create_empty_dashboard_html("No charts available")
        
        print(f"Creating simple dashboard with {len(successful_charts)} charts...")
        
        html_parts = []
        
        # Header
        html_parts.append(f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
        .dashboard-header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .dashboard-header h1 {{ margin: 0; font-size: 32px; font-weight: 600; }}
        .dashboard-header p {{ margin: 10px 0 0 0; font-size: 16px; opacity: 0.9; }}
        .chart-container {{ background: white; padding: 20px; margin-bottom: 30px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .chart-title {{ font-size: 18px; font-weight: 600; color: #333; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #667eea; }}
        .chart-content {{ width: 100%; min-height: 400px; }}
        .chart-info {{ font-size: 14px; color: #666; margin-bottom: 10px; font-style: italic; }}
    </style>
</head>
<body>
    <div class="dashboard-header">
        <h1>{title}</h1>
        <p>Total charts: {len(successful_charts)}</p>
    </div>
""")

        # Add each chart
        for i, chart_result in enumerate(successful_charts, 1):
            try:
                chart_type = chart_result.get('chart_type', 'Chart').title()
                question = chart_result.get('question', f'Chart {i}')
                chart_html_path = chart_result.get('chart_html_path')
                
                if not chart_html_path and output_dir:
                    individual_charts_dir = os.path.join(output_dir, 'individual_charts')
                    if os.path.exists(individual_charts_dir):
                        chart_files = list(Path(individual_charts_dir).glob(f"{i:02d}_*.html"))
                        if chart_files:
                            chart_html_path = str(chart_files[0])
                
                if chart_html_path and os.path.exists(chart_html_path):
                    with open(chart_html_path, 'r', encoding='utf-8') as f:
                        chart_html = f.read()
                    
                    start_idx = chart_html.find('<div>')
                    end_idx = chart_html.find('</body>')
                    
                    if start_idx != -1 and end_idx != -1:
                        chart_div = chart_html[start_idx:end_idx]
                    else:
                        chart_div = chart_html
                    
                    html_parts.append(f"""
    <div class="chart-container">
        <div class="chart-title">📊 {chart_type}: {question}</div>
        <div class="chart-info">Chart #{i}</div>
        <div class="chart-content">
            {chart_div}
        </div>
    </div>
""")
                    print(f"  ✓ Added chart {i}: {chart_type}")
                else:
                    print(f"  ✗ Chart file not found: {chart_html_path}")
            except Exception as e:
                print(f"  ✗ Error adding chart {i}: {e}")
        
        html_parts.append("</body></html>")
        return ''.join(html_parts)
    
    def _create_empty_dashboard_html(self, message: str) -> str:
        """Tạo HTML dashboard trống"""
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Dashboard Error</title>
    <style>
        body {{ font-family: Arial, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #f5f5f5; }}
        .error-message {{ background: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; color: #d32f2f; font-size: 20px; }}
    </style>
</head>
<body>
    <div class="error-message">{message}</div>
</body>
</html>
"""
    
    def create_summary_dashboard(self,
                               chart_results: List[Dict[str, Any]],
                               analysis_summary: Dict[str, Any],
                               output_dir: str = None) -> str:
        """Create summary dashboard with overall statistics"""
        
        successful_charts = [r for r in chart_results if r.get('success', False)]
        total_questions = analysis_summary.get('total_questions', len(chart_results))
        failed_count = total_questions - len(successful_charts)
        exec_time = analysis_summary.get('execution_time', 0)
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Dashboard Summary</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
        .summary-header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .summary-header h1 {{ margin: 0; font-size: 32px; font-weight: 600; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .stat-card {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }}
        .stat-value {{ font-size: 36px; font-weight: bold; color: #667eea; margin: 10px 0; }}
        .stat-label {{ font-size: 14px; color: #666; text-transform: uppercase; letter-spacing: 1px; }}
    </style>
</head>
<body>
    <div class="summary-header">
        <h1>📊 Dashboard Summary Report</h1>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-label">Total Charts</div>
            <div class="stat-value">{len(successful_charts)}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Success Rate</div>
            <div class="stat-value">{(len(successful_charts)/total_questions*100):.1f}%</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Failed Charts</div>
            <div class="stat-value" style="color: #e74c3c;">{failed_count}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Execution Time</div>
            <div class="stat-value">{exec_time:.1f}s</div>
        </div>
    </div>
</body>
</html>
"""
        return html


if __name__ == "__main__":
    pass
