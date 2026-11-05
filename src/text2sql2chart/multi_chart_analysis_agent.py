"""
🚀 Multi-Chart Analysis Agent

Main workflow integrating all components:
DatabaseAnalyzer → QuestionGenerator → MultiChartAgent → DashboardGenerator

Usage:
    agent = MultiChartAnalysisAgent(vanna_instance, api_key)
    result = agent.analyze("Show me charts for this database")
"""

import os
import json
import time
from typing import Dict, List, Any, Optional

from text2sql2chart.database_analyzer import DatabaseAnalyzer
from text2sql2chart.question_generator import QuestionGenerator
from text2sql2chart.multi_chart_agent import MultiChartAgent
from text2sql2chart.dashboard_generator import DashboardGenerator
from text2sql2chart.query_transformer import QueryTransformer
from text2sql2chart.grafana_generator import GrafanaDashboardGenerator


class MultiChartAnalysisAgent:
    """
    Main agent orchestrating the entire multi-chart analysis workflow
    """

    def __init__(self, vanna_instance, api_key: str, model: str = None, provider: str = "openai"):
        """
        Initialize with Vanna instance and AI provider credentials
        """
        self.vn = vanna_instance
        self.api_key = api_key
        self.provider = provider

        # Initialize all components
        print("Initializing Multi-Chart Analysis Agent...")
        self.db_analyzer = DatabaseAnalyzer(vanna_instance)
        self.question_generator = QuestionGenerator(api_key, model, provider=provider)
        self.multi_chart_agent = MultiChartAgent(api_key, model, provider=provider)
        self.dashboard_generator = DashboardGenerator()
        self.query_transformer = QueryTransformer(api_key, model, provider=provider)
        self.grafana_generator = GrafanaDashboardGenerator()
        
        # Set vanna instance for multi chart agent
        self.multi_chart_agent.set_vanna_instance(vanna_instance)
        
        # Cache for database analysis
        self._database_analyzed = False
        self._db_analysis_cache = None
        
        print("Multi-Chart Analysis Agent ready!")
    
    def analyze(self, 
                user_request: str,
                max_charts: int = 5,
                analysis_mode: str = 'smart',
                dashboard_theme: str = 'modern',
                query_transform_method: Optional[str] = None) -> Dict[str, Any]:
        """
        Main analysis workflow
        
        Args:
            user_request: User's general request (e.g., "Show me charts for this database")
            max_charts: Maximum number of charts to generate
            analysis_mode: 'smart' (AI-generated) or 'pattern' (pattern-based) or 'both'
            dashboard_theme: 'modern', 'corporate', 'pastel', 'default'
            query_transform_method: Query transformation method - None, 'rewriting', 'step_back', 'decomposition', 'compare_all', or 'rank_by_similarity'
            
        Returns:
            Complete analysis results with dashboard
        """
        
        print(f"Starting Multi-Chart Analysis")
        print(f"User Request: '{user_request}'")
        print(f"Settings: {max_charts} charts, {analysis_mode} mode, {dashboard_theme} theme")
        if query_transform_method:
            print(f"Query Transform: {query_transform_method}")
        print("="*80)
        
        start_time = time.time()
        
        try:
            # Step 0: Query Transformation (if enabled)
            transformed_query = user_request
            query_transform_result = None
            
            if query_transform_method:
                print("\nSTEP 0: QUERY TRANSFORMATION")
                query_transform_result = self._transform_query(user_request, query_transform_method)
                transformed_query = query_transform_result.get('transformed_query', user_request)
                print(f"   Original: {user_request}")
                print(f"   Transformed: {transformed_query}")
            
            # Step 1: Analyze Database Structure
            print("\nSTEP 1: DATABASE ANALYSIS")
            db_analysis = self._analyze_database()
            
            # Step 2: Generate Analysis Questions  
            print("\nSTEP 2: QUESTION GENERATION")
            questions = self._generate_questions(transformed_query, db_analysis, max_charts, analysis_mode)
            
            # Step 3: Create Multiple Charts
            print("\nSTEP 3: MULTI-CHART CREATION")
            chart_results = self._create_charts(questions)
            
            # Step 4: Generate Dashboard
            print("\nSTEP 4: DASHBOARD GENERATION")
            dashboard = self._create_dashboard(chart_results, user_request, dashboard_theme)
            
            # Step 5: Create Summary
            print("\nSTEP 5: SUMMARY GENERATION")
            summary = self._generate_analysis_summary(chart_results, start_time)
            
            print(f"\nANALYSIS COMPLETED!")
            print(f"Total Time: {time.time() - start_time:.2f} seconds")
            print("="*80)
            
            result = {
                'success': True,
                'user_request': user_request,
                'database_analysis': db_analysis,
                'questions': questions,
                'chart_results': chart_results,
                'dashboard': dashboard,
                'summary': summary,
                'execution_time': time.time() - start_time,
                'settings': {
                    'max_charts': max_charts,
                    'analysis_mode': analysis_mode,
                    'dashboard_theme': dashboard_theme,
                    'query_transform_method': query_transform_method
                }
            }
            
            # Add query transformation result if available
            if query_transform_result:
                result['query_transformation'] = query_transform_result
            
            return result
            
        except Exception as e:
            print(f"Analysis failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'user_request': user_request,
                'execution_time': time.time() - start_time
            }
    
    def _transform_query(self, user_request: str, method: str) -> Dict[str, Any]:
        """
        Transform user query using specified method
        
        Args:
            user_request: Original user query
            method: Transformation method - 'rewriting', 'step_back', 'decomposition', 'compare_all', or 'rank_by_similarity'
        
        Returns:
            Transformation result
        """
        
        try:
            # Get database schema for context
            db_schema = None
            if self._db_analysis_cache:
                db_schema = self._db_analysis_cache.get('summary_text', None)
            
            if method == 'compare_all':
                # Compare all three methods
                result = self.query_transformer.transform_and_compare(user_request, db_schema)
                # Use the recommended primary method's result
                primary_method = result['recommendations']['primary_method']
                return result['transformations'][primary_method]
            elif method == 'rank_by_similarity':
                # Rank by semantic similarity to original and pick closest
                result = self.query_transformer.rank_by_similarity(user_request, db_schema)
                # Ensure returned structure is aligned with other methods
                return {
                    'method': f"rank_by_similarity_selected_{result.get('selected', {}).get('method', 'unknown')}",
                    'original_query': result.get('original_query', user_request),
                    'transformed_query': result.get('transformed_query', user_request),
                    'metadata': {
                        'ranking': result.get('ranking', []),
                        'selected': result.get('selected', {})
                    },
                    'success': result.get('success', True)
                }
            else:
                # Use specific method
                return self.query_transformer.transform_query(user_request, method, db_schema)
        
        except Exception as e:
            print(f"Query transformation failed: {e}")
            return {
                'method': method,
                'original_query': user_request,
                'transformed_query': user_request,
                'success': False,
                'error': str(e)
            }
    
    def _analyze_database(self) -> Dict[str, Any]:
        """
        Analyze database structure (with caching)
        """
        
        if self._database_analyzed and self._db_analysis_cache:
            print("Using cached database analysis")
            return self._db_analysis_cache
        
        print("Analyzing database structure...")
        
        try:
            # Ensure database connection exists
            if not hasattr(self.vn, 'run_sql'):
                raise Exception("Vanna instance does not have run_sql method")
                
            # Test database connection with a simple query
            try:
                test_result = self.vn.run_sql("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
                print(f"Database connection verified: {len(test_result)} tables found")
            except Exception as conn_e:
                raise Exception(f"Database connection failed: {conn_e}")
            
            db_analysis = self.db_analyzer.analyze_database_structure()
            db_summary = self.db_analyzer.get_analysis_summary()
            
            result = {
                'analysis': db_analysis,
                'summary_text': db_summary,
                'tables_count': len(db_analysis.get('tables', [])),
                'total_relationships': sum(len(rels) for rels in db_analysis.get('relationships', {}).values())
            }
            
            # Cache result
            self._database_analyzed = True
            self._db_analysis_cache = result
            
            print(f"Database analyzed: {result['tables_count']} tables, {result['total_relationships']} relationships")
            return result
            
        except Exception as e:
            print(f"Database analysis failed: {e}")
            return {'error': str(e), 'analysis': {}, 'summary_text': 'Database analysis failed'}
    
    def _generate_questions(self, 
                          user_request: str,
                          db_analysis: Dict[str, Any], 
                          max_charts: int,
                          analysis_mode: str) -> List[Dict[str, Any]]:
        """
        Generate analysis questions based on mode
        """
        
        questions = []
        
        try:
            if analysis_mode in ['smart', 'both']:
                print("Generating AI-powered questions...")
                
                db_summary = db_analysis.get('summary_text', '')
                ai_questions = self.question_generator.generate_analysis_questions(
                    user_request, db_summary, max_questions=max_charts
                )
                questions.extend(ai_questions)
                print(f"Generated {len(ai_questions)} AI questions")
            
            if analysis_mode in ['pattern', 'both']:
                print("Generating pattern-based questions...")
                
                data_patterns = db_analysis.get('analysis', {}).get('patterns', {})
                pattern_questions = self.question_generator.generate_questions_from_patterns(
                    data_patterns, user_request
                )
                questions.extend(pattern_questions)
                print(f"Generated {len(pattern_questions)} pattern questions")
            
            if not questions:
                print("No questions generated, using fallback questions")
                questions = self.question_generator._generate_fallback_questions()
            
            # Prioritize and limit questions
            final_questions = self.question_generator.prioritize_questions(questions, max_charts)
            
            print(f"Final question set: {len(final_questions)} questions")
            for i, q in enumerate(final_questions, 1):
                print(f"  {i}. [{q.get('chart_type', 'chart')}] {q.get('question', 'Unknown')}")
            
            return final_questions
            
        except Exception as e:
            print(f"Question generation failed: {e}")
            return self.question_generator._generate_fallback_questions()
    
    def _create_charts(self, questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create multiple charts from questions
        """
        
        try:
            results = self.multi_chart_agent.create_multiple_charts(questions, max_parallel=2)
            
            success_count = len(results['successful_charts'])
            total_count = len(questions)
            
            print(f"Chart creation completed: {success_count}/{total_count} successful")
            
            return results
            
        except Exception as e:
            print(f"Chart creation failed: {e}")
            return {
                'successful_charts': [],
                'failed_charts': [{'question': q, 'error': str(e)} for q in questions],
                'summary': {'total_questions': len(questions), 'successful_charts': 0, 'failed_charts': len(questions)}
            }
    
    def _create_dashboard(self, 
                        chart_results: Dict[str, Any],
                        user_request: str, 
                        theme: str) -> Dict[str, Any]:
        """
        Create dashboard from chart results
        """
        
        successful_charts = chart_results.get('successful_charts', [])
        
        if not successful_charts:
            print("No successful charts to create dashboard")
            return {'dashboard': None, 'summary_dashboard': None, 'error': 'No charts available'}
        
        print(f"Creating dashboard with {len(successful_charts)} charts...")
        
        try:
            # Main dashboard
            dashboard_title = f"Analysis Dashboard: {user_request}..."
            main_dashboard = self.dashboard_generator.create_dashboard(
                successful_charts, 
                title=dashboard_title,
                theme=theme,
                layout_style='auto'
            )
            
            # Summary dashboard
            summary_dashboard = self.dashboard_generator.create_summary_dashboard(
                successful_charts, 
                chart_results.get('summary', {})
            )
            
            print("Dashboard created successfully!")
            
            return {
                'main_dashboard': main_dashboard,
                'summary_dashboard': summary_dashboard,
                'chart_count': len(successful_charts),
                'theme': theme
            }
            
        except Exception as e:
            print(f"Dashboard creation failed: {e}")
            return {'error': str(e), 'main_dashboard': None, 'summary_dashboard': None}
    
    def _generate_analysis_summary(self, 
                                 chart_results: Dict[str, Any], 
                                 start_time: float) -> Dict[str, Any]:
        """
        Generate comprehensive analysis summary
        """
        
        execution_time = time.time() - start_time
        successful_charts = chart_results.get('successful_charts', [])
        failed_charts = chart_results.get('failed_charts', [])
        
        # Chart type distribution
        chart_types = {}
        for chart in successful_charts:
            chart_type = chart.get('chart_type', 'unknown')
            chart_types[chart_type] = chart_types.get(chart_type, 0) + 1
        
        # Data summary
        total_data_rows = sum(chart.get('data_shape', (0, 0))[0] for chart in successful_charts)
        total_data_cols = sum(chart.get('data_shape', (0, 0))[1] for chart in successful_charts)
        
        summary = {
            'execution_time': execution_time,
            'total_questions': len(successful_charts) + len(failed_charts),
            'successful_charts': len(successful_charts),
            'failed_charts': len(failed_charts),
            'success_rate': len(successful_charts) / max(1, len(successful_charts) + len(failed_charts)) * 100,
            'chart_type_distribution': chart_types,
            'total_data_processed': {
                'rows': total_data_rows,
                'columns': total_data_cols
            },
            'performance_metrics': {
                'avg_time_per_chart': execution_time / max(1, len(successful_charts)),
                'charts_per_minute': len(successful_charts) / max(1, execution_time / 60)
            }
        }

        print("Analysis Summary:")
        print(f"  Success Rate: {summary['success_rate']:.1f}%")
        print(f"  Avg Time per Chart: {summary['performance_metrics']['avg_time_per_chart']:.2f}s")
        print(f"  Chart Types: {list(chart_types.keys())}")

        return summary

    def save_results(self, results: Dict[str, Any], output_dir: str = "analysis_output"):
        """
        Save analysis results to files
        """
        if not results.get('success'):
            print("Cannot save failed analysis results")
            return
            
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        print(f"Saving results to {output_dir}/...")

        try:
            # Save individual charts FIRST
            chart_results = results.get('chart_results', {})
            if chart_results.get('successful_charts'):
                charts_dir = os.path.join(output_dir, "individual_charts")
                self.multi_chart_agent.save_charts_individually(
                    chart_results['successful_charts'], 
                    charts_dir
                )
            
            # NOW create dashboard with output_dir so it can find the charts
            if chart_results.get('successful_charts'):
                print("Creating dashboard from saved charts...")
                dashboard_title = f"Analysis Dashboard: {results['user_request']}"
                main_dashboard_html = self.dashboard_generator.create_dashboard(
                    chart_results['successful_charts'],
                    title=dashboard_title,
                    theme=results.get('settings', {}).get('dashboard_theme', 'modern'),
                    output_dir=output_dir
                )
                
                # Save main dashboard
                main_dashboard_path = os.path.join(output_dir, "main_dashboard.html")
                with open(main_dashboard_path, 'w', encoding='utf-8') as f:
                    f.write(main_dashboard_html)
                print(f"  Main dashboard: {main_dashboard_path}")
                
                # Create and save summary dashboard
                summary_dashboard_html = self.dashboard_generator.create_summary_dashboard(
                    chart_results['successful_charts'],
                    results.get('summary', {}),
                    output_dir=output_dir
                )
                summary_dashboard_path = os.path.join(output_dir, "summary_dashboard.html")
                with open(summary_dashboard_path, 'w', encoding='utf-8') as f:
                    f.write(summary_dashboard_html)
                print(f"  Summary dashboard: {summary_dashboard_path}")
            
            # Save analysis report
            report_path = os.path.join(output_dir, "analysis_report.json")
            
            # Prepare JSON-serializable data
            json_data = {
                'user_request': results['user_request'],
                'summary': results['summary'],
                'questions': results['questions'],
                'settings': results['settings'],
                'execution_time': results['execution_time']
            }
            
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)

            print(f"  Analysis report: {report_path}")
            print(f"Results saved successfully to {output_dir}/")

        except Exception as e:
            print(f"Error saving results: {e}")

    def save_results_with_grafana(self,
                                  results: Dict[str, Any],
                                  output_dir: str = "analysis_output",
                                  grafana_datasource: str = "json",
                                  database_path: str = None):
        """
        Save analysis results with Grafana dashboard generation

        Args:
            results: Analysis results from analyze()
            output_dir: Output directory
            grafana_datasource: Grafana datasource type ('json', 'csv', 'sqlite')
            database_path: Path to database file (for SQLite datasource)
        """

        # First save regular results
        self.save_results(results, output_dir)

        if not results.get('success'):
            return

        # Generate Grafana dashboard
        print("\n" + "="*60)
        print("GENERATING GRAFANA DASHBOARD")
        print("="*60)

        try:
            chart_results = results.get('chart_results', {})
            successful_charts = chart_results.get('successful_charts', [])

            if successful_charts:
                grafana_dir = os.path.join(output_dir, "grafana")

                dashboard_title = f"Analysis: {results['user_request'][:50]}"

                grafana_result = self.grafana_generator.create_grafana_dashboard(
                    successful_charts,
                    title=dashboard_title,
                    datasource_type=grafana_datasource,
                    output_dir=grafana_dir
                )

                # Create datasource config
                self.grafana_generator.create_datasource_config(
                    datasource_type=grafana_datasource,
                    database_path=database_path,
                    output_dir=grafana_dir
                )

                # Create provisioning files if PyYAML is available
                try:
                    self.grafana_generator.create_provisioning_files(
                        grafana_result,
                        self.grafana_generator.create_datasource_config(
                            grafana_datasource,
                            database_path,
                            grafana_dir
                        ),
                        grafana_dir
                    )
                except ImportError:
                    print("⚠ PyYAML not installed - skipping provisioning files")

                print(f"\n✓ Grafana dashboard generated in: {grafana_dir}")
                print(f"  Dashboard JSON: {grafana_dir}/grafana_dashboard.json")
                print(f"  Data files: {grafana_dir}/data/")

            else:
                print("No successful charts to generate Grafana dashboard")

        except Exception as e:
            print(f"Error generating Grafana dashboard: {e}")
            import traceback
            traceback.print_exc()


# Convenience function
def create_multi_chart_agent(vanna_instance, api_key: str, provider: str = "openai") -> MultiChartAnalysisAgent:
    """
    Convenience function to create agent
    """
    return MultiChartAnalysisAgent(vanna_instance, api_key, provider=provider)


if __name__ == "__main__":
    # Example usage (will be tested in notebook)
    print("Multi-Chart Analysis Agent")
    print("Usage: agent = create_multi_chart_agent(vn, api_key)")
    print("       result = agent.analyze('Show me charts for this database')")