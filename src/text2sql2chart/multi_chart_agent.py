import os
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, List, Any, Tuple
import time

from text2sql2chart.chart_agent import ChartAgent
from text2sql2chart.utils import validate_dataframe


class MultiChartAgent:
    """
    Extends ChartAgent to handle multiple questions and create multiple charts at once
    """

    def __init__(self, api_key: str, model: str = None, provider: str = "openai"):
        self.chart_agent = ChartAgent(api_key=api_key, model=model, provider=provider)
        self.vn = None  # Will be set from outside
        
    def set_vanna_instance(self, vanna_instance):
        """Set Vanna instance to query database"""
        self.vn = vanna_instance
    
    def create_multiple_charts(self,
                             questions: List[Dict[str, Any]],
                             max_parallel: int = 3) -> Dict[str, Any]:
        """
        Create multiple charts from list of questions

        Args:
            questions: List of question dictionaries
            max_parallel: Number of charts to create in parallel

        Returns:
            Dictionary containing results of all charts
        """
        
        print(f"Creating {len(questions)} charts...")
        print("="*60)
        
        results = {
            'successful_charts': [],
            'failed_charts': [],
            'summary': {},
            'execution_time': 0
        }
        
        start_time = time.time()

        # Process questions in batches to avoid overload
        batch_size = max_parallel
        
        for i in range(0, len(questions), batch_size):
            batch = questions[i:i + batch_size]
            print(f"\nProcessing batch {i//batch_size + 1}: Questions {i+1}-{min(i+batch_size, len(questions))}")

            # Process batch with threading
            batch_results = self._process_question_batch(batch)
            
            # Merge results
            results['successful_charts'].extend(batch_results['successful'])
            results['failed_charts'].extend(batch_results['failed'])
            
            # Progress update
            success_count = len(results['successful_charts'])
            total_processed = len(results['successful_charts']) + len(results['failed_charts'])
            print(f"Progress: {success_count}/{total_processed} successful")
        
        # Final summary
        end_time = time.time()
        results['execution_time'] = end_time - start_time
        results['summary'] = {
            'total_questions': len(questions),
            'successful_charts': len(results['successful_charts']),
            'failed_charts': len(results['failed_charts']),
            'success_rate': len(results['successful_charts']) / len(questions) * 100,
            'execution_time': results['execution_time']
        }
        
        print(f"\nMULTI-CHART CREATION COMPLETED!")
        print(f"Success: {results['summary']['successful_charts']}/{results['summary']['total_questions']} charts")
        print(f"Time: {results['summary']['execution_time']:.2f} seconds")
        print(f"Success Rate: {results['summary']['success_rate']:.1f}%")
        
        return results
    
    def _process_question_batch(self, questions: List[Dict[str, Any]]) -> Dict[str, List]:
        """
        Process a batch of questions with threading
        """
        batch_results = {'successful': [], 'failed': []}

        # Sequential processing to avoid overwhelming OpenAI API
        for question_dict in questions:
            try:
                result = self._process_single_question(question_dict)
                if result and result.get('figure'):
                    batch_results['successful'].append(result)
                else:
                    batch_results['failed'].append({
                        'question': question_dict,
                        'error': 'No figure generated'
                    })
            except Exception as e:
                batch_results['failed'].append({
                    'question': question_dict,
                    'error': str(e)
                })
                print(f"Error processing question '{question_dict.get('question', 'Unknown')}': {e}")
        
        return batch_results
    
    def _process_single_question(self, question_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single question and create chart
        """
        question = question_dict.get('question', '')
        print('-'*40)
        print(f"Processing question: {question}")
        print('-'*40)

        try:
            # Step 1: Text to SQL + Get Data with Vanna
            # Use generate_sql + run_sql directly to avoid Vanna's built-in
            # chart generation (we use our own ChartAgent instead)
            sql_query = self.vn.generate_sql(question)
            if not sql_query:
                print(f"    No SQL generated for question")
                return None
            # Strip language tag prefix that LLMs sometimes prepend (e.g. "sqlite\n...")
            sql_cleaned = sql_query.strip()
            first_line = sql_cleaned.splitlines()[0].strip().lower()
            if first_line in ('sqlite', 'sql', 'sqlite3') and not first_line.startswith('select'):
                sql_query = '\n'.join(sql_cleaned.splitlines()[1:]).strip()
            print(f"    SQL: {sql_query[:120]}...")
            df = self.vn.run_sql(sql_query)

            if not validate_dataframe(df, context=f"question '{question}'"):
                return None
            
            # Step 2: Create chart with ChartAgent
            chart_code, figure = self.chart_agent.create_chart(question, df)
            
            if figure:
                result = {
                    'question_info': question_dict,
                    'question': question,
                    'sql_query': sql_query,
                    'data': df,
                    'data_shape': df.shape,
                    'chart_code': chart_code,
                    'figure': figure,
                    'chart_type': question_dict.get('chart_type', 'unknown'),
                    'success': True
                }
                
                print(f"    Success: {df.shape[0]} rows → {question_dict.get('chart_type', 'chart')}")
                return result
            else:
                print(f"    Chart creation failed")
                return None
                
        except Exception as e:
            print(f"    Error: {e}")
            return None
    
    def generate_summary_report(self, results: Dict[str, Any]) -> str:
        """
        Create summary report about the chart creation process
        """
        
        summary = results['summary']
        successful_charts = results['successful_charts']
        failed_charts = results['failed_charts']
        
        report_lines = [
            "MULTI-CHART ANALYSIS REPORT",
            "="*50,
            f"Total Questions Processed: {summary['total_questions']}",
            f"Successful Charts: {summary['successful_charts']}",
            f"Failed Charts: {summary['failed_charts']}",
            f"Success Rate: {summary['success_rate']:.1f}%",
            f"Execution Time: {summary['execution_time']:.2f} seconds",
            "",
            "SUCCESSFUL CHARTS:",
        ]
        
        for i, chart in enumerate(successful_charts, 1):
            question = chart['question']
            chart_type = chart.get('chart_type', 'unknown')
            data_shape = chart.get('data_shape', (0, 0))
            
            report_lines.append(f"  {i}. {question[:60]}...")
            report_lines.append(f"     Type: {chart_type} | Data: {data_shape[0]} rows × {data_shape[1]} cols")
        
        if failed_charts:
            report_lines.extend([
                "",
                "FAILED CHARTS:",
            ])
            
            for i, failure in enumerate(failed_charts, 1):
                question = failure['question'].get('question', 'Unknown question')
                error = failure.get('error', 'Unknown error')
                
                report_lines.append(f"  {i}. {question[:60]}...")
                report_lines.append(f"     Error: {error}")
        
        report_lines.extend([
            "",
            "Analysis completed successfully!"
        ])
        
        return "\n".join(report_lines)
    
    def save_charts_individually(self, chart_results: List[Dict[str, Any]],
                               output_dir: str = "charts_output"):
        """
        Save each chart individually to files
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        successful_charts = [r for r in chart_results if r.get('success')]
        
        for i, chart_result in enumerate(successful_charts):
            try:
                figure = chart_result['figure']
                question = chart_result['question']
                chart_type = chart_result.get('chart_type', 'chart')
                
                # Clean filename
                filename = f"{i+1:02d}_{chart_type}_{question}"
                filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_')).rstrip()
                filename = filename.replace(' ', '_') + '.html'
                
                filepath = os.path.join(output_dir, filename)
                figure.write_html(filepath)
                
                print(f"Saved: {filepath}")
                
            except Exception as e:
                print(f"Error saving chart {i+1}: {e}")

        print(f"Charts saved to {output_dir}/")


if __name__ == "__main__":
    # Test
    pass