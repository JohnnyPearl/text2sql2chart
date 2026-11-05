import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import json
from typing import Dict, Any, Tuple

from text2sql2chart.utils import clean_markdown_code_blocks, create_openai_compatible_client

class ChartAgent:
    def __init__(self, api_key: str, model: str = None, provider: str = "openai"):
        """
        AI Agent specialized in data visualization
        Completely separate from Vanna - only receives DataFrame and generates chart code
        """
        self.client, default_model = create_openai_compatible_client(api_key, provider)
        self.model = model if model is not None else default_model
    
    def create_data_profile(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Create data profile instead of sending raw data (saves tokens)
        """
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        datetime_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
        
        profile = {
            'shape': df.shape,
            'columns': {
                'numeric': numeric_cols,
                'categorical': categorical_cols,
                'datetime': datetime_cols
            },
            'sample_data': df.head(3).to_dict('records'),
            'null_counts': df.isnull().sum().to_dict(),
        }

        # Add stats for numeric columns
        if numeric_cols:
            profile['numeric_stats'] = df[numeric_cols].describe().to_dict()

        # Add unique counts for categorical columns
        if categorical_cols:
            profile['categorical_info'] = {
                col: {
                    'unique_count': df[col].nunique(),
                    'top_values': df[col].value_counts().head(5).to_dict()
                } for col in categorical_cols
            }
        
        return profile
    
    def recommend_chart_type(self, question: str, data_profile: Dict) -> Dict[str, Any]:
        """
        Use AI to recommend appropriate chart type
        """
        prompt = f"""
        Analyze this user question and data profile to recommend the most appropriate chart type.

        USER QUESTION: "{question}"

        DATA PROFILE:
        - Shape: {data_profile['shape']} (rows, columns)
        - Numeric columns: {data_profile['columns']['numeric']}
        - Categorical columns: {data_profile['columns']['categorical']}
        - Datetime columns: {data_profile['columns']['datetime']}
        - Sample data: {data_profile['sample_data']}

        Based on the question intent and data characteristics, recommend:
        1. Chart type (bar, line, scatter, pie, histogram, box, etc.)
        2. Which columns to use for x, y, color, etc.
        3. Brief reasoning

        Respond in JSON format:
        {{
            "chart_type": "bar|line|scatter|pie|histogram|box|heatmap",
            "columns": {{
                "x": "column_name",
                "y": "column_name", 
                "color": "column_name_optional",
                "size": "column_name_optional"
            }},
            "reasoning": "Why this chart type fits the question and data",
            "title": "Suggested chart title"
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            content = response.choices[0].message.content.strip()

            # Clean up response - remove markdown code blocks if present
            content = clean_markdown_code_blocks(content, 'json')
            
            try:
                recommendation = json.loads(content)
                return recommendation
            except json.JSONDecodeError as je:
                print(f"JSON parsing error: {je}")
                print(f"Raw content: {content}")
                # Return fallback
                raise je
            
        except Exception as e:
            print(f"Error in chart recommendation: {e}")
            # Fallback recommendation based on data profile
            numeric_cols = data_profile['columns']['numeric']
            categorical_cols = data_profile['columns']['categorical']
            
            if len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
                chart_type = "bar"
                x_col = categorical_cols[0]
                y_col = numeric_cols[0]
            elif len(numeric_cols) >= 2:
                chart_type = "scatter"
                x_col = numeric_cols[0]
                y_col = numeric_cols[1]
            elif len(numeric_cols) >= 1:
                chart_type = "histogram"
                x_col = numeric_cols[0]
                y_col = None
            else:
                chart_type = "bar"
                x_col = categorical_cols[0] if categorical_cols else list(data_profile['sample_data'][0].keys())[0]
                y_col = None
                
            return {
                "chart_type": chart_type,
                "columns": {"x": x_col, "y": y_col},
                "reasoning": "Intelligent fallback based on data structure",
                "title": f"Data Visualization: {question}"
            }
    
    def generate_chart_code(self, recommendation: Dict, df_sample: pd.DataFrame) -> str:
        """
        Generate Plotly code based on recommendation
        """
        prompt = f"""
        Generate Python code using Plotly to create a chart based on this recommendation:

        CHART RECOMMENDATION: {json.dumps(recommendation, indent=2)}

        SAMPLE DATA (first few rows):
        {df_sample.to_string()}

        DATA TYPES:
        {df_sample.dtypes.to_dict()}

        Requirements:
        1. Use plotly.express (import as px)
        2. The DataFrame variable name is 'df'
        3. Create a complete, executable code block
        4. Include proper titles, labels, and formatting
        5. Handle any potential data issues (nulls, etc.)
        6. Make the chart interactive and visually appealing
        7. IMPORTANT: For legend title font settings, use fig.update_layout(legend=dict(title=dict(font=dict(size=14))))
           NOT legend.title.fontsize (which is invalid)
        8. For axis labels, use fig.update_xaxes(title_font=dict(size=12)) and fig.update_yaxes(title_font=dict(size=12))

        Return ONLY the Python code, no explanations:
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            code = response.choices[0].message.content.strip()
            # Remove code blocks if present
            code = clean_markdown_code_blocks(code, 'python')

            # Fix common Plotly syntax errors
            code = self._fix_plotly_syntax(code)

            return code

        except Exception as e:
            print(f"Error generating chart code: {e}")
            return "# Error generating chart code"

    def _fix_plotly_syntax(self, code: str) -> str:
        """
        Fix common Plotly syntax errors in generated code

        Common issues:
        - legend.title.fontsize (invalid) → legend=dict(title=dict(font=dict(size=...)))
        - fontsize= (invalid) → font=dict(size=...)
        """
        import re

        # Fix: legend.title.fontsize = <value>
        # Example: legend.title.fontsize = 14 → legend=dict(title=dict(font=dict(size=14)))
        code = re.sub(
            r'legend\.title\.fontsize\s*=\s*(\d+)',
            r'legend=dict(title=dict(font=dict(size=\1)))',
            code
        )

        # Fix: fontsize= parameter (general)
        # Example: fontsize = 12 → font=dict(size=12)
        code = re.sub(
            r'(?:title_)?fontsize\s*=\s*(\d+)',
            r'font=dict(size=\1)',
            code
        )

        return code

    def create_chart(self, question: str, df: pd.DataFrame) -> Tuple[str, Any]:
        """
        Main method: from question + DataFrame → chart code + figure
        """
        print("-" * 40)
        print("Starting chart creation process...")
        # Step 1: Create data profile (save tokens)
        print("[1] Analyzing data structure...")
        data_profile = self.create_data_profile(df)

        # Step 2: AI recommends chart type
        print("[2] AI recommending chart type...")
        recommendation = self.recommend_chart_type(question, data_profile)
        print(f"Recommended: {recommendation['chart_type']} - {recommendation['reasoning']}")

        # Step 3: Generate code with sample data
        print("[3] Generating chart code...")
        sample_df = df.head(10)  # Only use sample data to generate code
        chart_code = self.generate_chart_code(recommendation, sample_df)

        # Step 4: Execute code with full data
        print("[4] Creating chart...")
        try:
            # Strip .show() calls — they fail in headless/non-IPython environments
            sanitized_code = '\n'.join(
                line for line in chart_code.splitlines()
                if not line.strip().startswith('fig.show(')
                and '.show()' not in line
            )
            # Create namespace to execute code (include make_subplots for multi-panel charts)
            from plotly.subplots import make_subplots
            namespace = {'df': df, 'px': px, 'go': go, 'pd': pd, 'np': np,
                         'make_subplots': make_subplots}
            exec(sanitized_code, namespace)

            # Find figure object in namespace — check 'fig' first, then scan all vars
            fig = namespace.get('fig')
            if fig is None or not hasattr(fig, '_layout'):
                for var_name, var_value in namespace.items():
                    if hasattr(var_value, '_layout') and hasattr(var_value, 'show'):
                        fig = var_value
                        break

            if fig is None:
                print(f"    No Plotly figure found in executed code")
            return chart_code, fig

        except Exception as e:
            print(f"Error executing chart code: {e}")
            return chart_code, None

if __name__ == "__main__":
    # Example usage (will test in notebook)
    pass
