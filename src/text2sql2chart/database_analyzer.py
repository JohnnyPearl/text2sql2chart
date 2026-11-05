import sqlite3
import pandas as pd
from typing import Dict, List, Any, Tuple
import json


class DatabaseAnalyzer:
    """
    Analyze database structure to understand data patterns,
    relationships and types of questions that can be asked
    """

    def __init__(self, vanna_instance=None):
        """
        Initialize with Vanna instance to use database connection
        """
        self.vn = vanna_instance
        self.schema_info = {}
        self.table_relationships = {}
        self.data_patterns = {}
    
    def analyze_database_structure(self) -> Dict[str, Any]:
        """
        Analyze entire database structure
        """
        print("Analyzing database structure...")

        # 1. Get list of all tables
        tables_df = self.vn.run_sql("SELECT name FROM sqlite_master WHERE type='table';")
        table_names = tables_df['name'].tolist()
        
        print(f"Found {len(table_names)} tables: {table_names}")

        # 2. Analyze each table
        for table in table_names:
            self.schema_info[table] = self._analyze_table_structure(table)

        # 3. Detect relationships
        self._detect_table_relationships()

        # 4. Analyze data patterns
        self._analyze_data_patterns()
        
        print("Database analysis completed!")
        return {
            'tables': table_names,
            'schema_info': self.schema_info,
            'relationships': self.table_relationships,
            'patterns': self.data_patterns
        }
    
    def _analyze_table_structure(self, table_name: str) -> Dict[str, Any]:
        """
        Analyze structure of a specific table
        """
        print(f"  Analyzing table: {table_name}")

        # Get schema info
        schema_df = self.vn.run_sql(f"PRAGMA table_info({table_name});")

        # Get sample data
        try:
            sample_df = self.vn.run_sql(f"SELECT * FROM {table_name} LIMIT 100;")
            row_count_df = self.vn.run_sql(f"SELECT COUNT(*) as count FROM {table_name};")
            row_count = row_count_df['count'].iloc[0]
        except Exception as e:
            print(f"Error getting sample data from {table_name}: {e}")
            sample_df = pd.DataFrame()
            row_count = 0

        # Classify columns
        numeric_columns = []
        categorical_columns = []
        text_columns = []
        id_columns = []
        
        for _, row in schema_df.iterrows():
            col_name = row['name']
            col_type = row['type'].upper()
            
            if 'ID' in col_name.upper() or row['pk']:  # Primary key or ID column
                id_columns.append(col_name)
            elif 'INT' in col_type or 'REAL' in col_type or 'FLOAT' in col_type:
                numeric_columns.append(col_name)
            elif 'TEXT' in col_type or 'VARCHAR' in col_type:
                # Distinguish categorical vs free text
                if not sample_df.empty and col_name in sample_df.columns:
                    unique_ratio = sample_df[col_name].nunique() / len(sample_df)
                    if unique_ratio < 0.5:  # If < 50% unique then consider as categorical
                        categorical_columns.append(col_name)
                    else:
                        text_columns.append(col_name)
                else:
                    text_columns.append(col_name)
        
        # Thống kê chi tiết cho sample data
        column_stats = {}
        if not sample_df.empty:
            for col in sample_df.columns:
                if col in numeric_columns:
                    column_stats[col] = {
                        'type': 'numeric',
                        'min': sample_df[col].min(),
                        'max': sample_df[col].max(),
                        'mean': sample_df[col].mean(),
                        'null_count': sample_df[col].isnull().sum()
                    }
                elif col in categorical_columns:
                    value_counts = sample_df[col].value_counts().head(10)
                    column_stats[col] = {
                        'type': 'categorical', 
                        'unique_count': sample_df[col].nunique(),
                        'top_values': value_counts.to_dict(),
                        'null_count': sample_df[col].isnull().sum()
                    }
                else:
                    column_stats[col] = {
                        'type': 'text',
                        'unique_count': sample_df[col].nunique(),
                        'null_count': sample_df[col].isnull().sum(),
                        'sample_values': sample_df[col].dropna().head(3).tolist()
                    }
        
        return {
            'schema': schema_df.to_dict('records'),
            'row_count': row_count,
            'column_types': {
                'numeric': numeric_columns,
                'categorical': categorical_columns, 
                'text': text_columns,
                'id': id_columns
            },
            'column_stats': column_stats,
            'sample_data': sample_df.head(5).to_dict('records') if not sample_df.empty else []
        }
    
    def _detect_table_relationships(self):
        """
        Detect relationships between tables based on column names and foreign keys
        """
        print("Detecting table relationships...")
        
        relationships = {}
        
        for table1, info1 in self.schema_info.items():
            relationships[table1] = []
            
            for table2, info2 in self.schema_info.items():
                if table1 == table2:
                    continue
                    
                # Tìm potential foreign key relationships
                id_cols1 = info1['column_types']['id']
                id_cols2 = info2['column_types']['id']
                all_cols1 = [col['name'] for col in info1['schema']]
                all_cols2 = [col['name'] for col in info2['schema']]


                # Check if there is a column name matching pattern
                for col1 in all_cols1:
                    for col2 in all_cols2:
                        # If table1 has column matching id name of table2
                        if col1.lower() in [f"{table2}_id", f"{table2}id"] or \
                           col2.lower() in [f"{table1}_id", f"{table1}id"] or \
                           (col1 == col2 and 'id' in col1.lower()):
                            
                            relationships[table1].append({
                                'related_table': table2,
                                'relationship_type': 'foreign_key',
                                'local_column': col1,
                                'foreign_column': col2,
                                'confidence': 'high'
                            })
        
        self.table_relationships = relationships
        print(f"Found {sum(len(rels) for rels in relationships.values())} potential relationships")
    
    def _analyze_data_patterns(self):
        """
        Phân tích patterns trong data để suggest các loại analysis
        """
        print("Analyzing data patterns...")
        
        patterns = {}
        
        for table_name, info in self.schema_info.items():
            table_patterns = []
            
            numeric_cols = info['column_types']['numeric']
            categorical_cols = info['column_types']['categorical']
            
            # Pattern 1: Distributions (cho numeric columns)
            if numeric_cols:
                table_patterns.append({
                    'type': 'distribution',
                    'columns': numeric_cols,
                    'description': f'Distribution analysis of numeric values in {table_name}',
                    'chart_suggestions': ['histogram', 'box_plot', 'violin_plot']
                })
            
            # Pattern 2: Categorical breakdowns
            if categorical_cols:
                table_patterns.append({
                    'type': 'categorical_breakdown',
                    'columns': categorical_cols,
                    'description': f'Categorical distribution in {table_name}',
                    'chart_suggestions': ['bar_chart', 'pie_chart', 'donut_chart']
                })
            
            # Pattern 3: Correlation patterns (nếu có >= 2 numeric columns)
            if len(numeric_cols) >= 2:
                table_patterns.append({
                    'type': 'correlation',
                    'columns': numeric_cols,
                    'description': f'Correlation analysis between numeric variables in {table_name}',
                    'chart_suggestions': ['scatter_plot', 'correlation_matrix', 'heatmap']
                })
            
            # Pattern 4: Cross-tabulation (numeric by categorical)
            if numeric_cols and categorical_cols:
                table_patterns.append({
                    'type': 'cross_analysis',
                    'numeric_columns': numeric_cols,
                    'categorical_columns': categorical_cols,
                    'description': f'Analysis of {numeric_cols} by {categorical_cols} in {table_name}',
                    'chart_suggestions': ['grouped_bar', 'box_plot_by_category', 'violin_plot']
                })
            
            patterns[table_name] = table_patterns
        
        self.data_patterns = patterns
        print("Data pattern analysis completed!")
    
    def get_analysis_summary(self) -> str:
        """
        Create summary text of entire database analysis for use with AI
        """
        summary_parts = []
        
        summary_parts.append(f"DATABASE ANALYSIS SUMMARY:")
        summary_parts.append(f"==========================")
        summary_parts.append(f"Total tables: {len(self.schema_info)}")
        
        for table_name, info in self.schema_info.items():
            summary_parts.append(f"\nTABLE: {table_name}")
            summary_parts.append(f"   - Rows: {info['row_count']}")
            summary_parts.append(f"   - Numeric columns: {info['column_types']['numeric']}")
            summary_parts.append(f"   - Categorical columns: {info['column_types']['categorical']}")
            summary_parts.append(f"   - Text columns: {info['column_types']['text']}")
            summary_parts.append(f"   - ID columns: {info['column_types']['id']}")
            
            # Top categorical values
            for col, stats in info['column_stats'].items():
                if stats['type'] == 'categorical' and 'top_values' in stats:
                    top_vals = list(stats['top_values'].keys())[:3]
                    summary_parts.append(f"   - {col} top values: {top_vals}")
        
        # Relationships
        summary_parts.append(f"\nTABLE RELATIONSHIPS:")
        for table, rels in self.table_relationships.items():
            if rels:
                for rel in rels:
                    summary_parts.append(f"   - {table}.{rel['local_column']} → {rel['related_table']}.{rel['foreign_column']}")
        
        return "\n".join(summary_parts)


if __name__ == "__main__":
    # Test with existing vanna instance
    pass