from typing import List, Dict, Any
import json

from text2sql2chart.utils import clean_markdown_code_blocks, create_openai_compatible_client


class QuestionGenerator:
    """
    Use AI to generate multiple data analysis questions
    based on database structure and user intent
    """

    def __init__(self, api_key: str, model: str = None, provider: str = "openai"):
        self.client, default_model = create_openai_compatible_client(api_key, provider)
        self.model = model if model is not None else default_model
        
    def generate_analysis_questions(self,
                                 user_intent: str,
                                 database_summary: str,
                                 max_questions: int = 6) -> List[Dict[str, Any]]:
        """
        Generate list of analysis questions based on user intent and database structure

        Args:
            user_intent: User's general question
            database_summary: Summary of database analysis
            max_questions: Maximum number of questions

        Returns:
            List of questions with metadata
        """
        
        prompt = f"""
        You are an expert data analyst. Based on the user's general request and the database structure, generate specific analytical questions that would create meaningful visualizations.

        USER REQUEST: "{user_intent}"

        DATABASE STRUCTURE:
        {database_summary}

        Generate {max_questions} specific, actionable questions that:
        1. Are directly answerable with the available data
        2. Would create meaningful and diverse visualizations  
        3. Cover different aspects of the data (distributions, relationships, comparisons, trends)
        4. Are specific enough to generate clear SQL queries
        5. Provide business/analytical insights

        For each question, also suggest:
        - The most appropriate chart type
        - Which tables/columns would be involved
        - The analytical insight it would provide

        Return your response as a JSON array with this structure:
        [
            {{
                "question": "Specific analytical question in English",
                "chart_type": "bar|pie|histogram|scatter|line|box|heatmap",
                "tables_involved": ["table1", "table2"],
                "columns_involved": ["col1", "col2"],
                "analysis_type": "distribution|comparison|correlation|trend|breakdown",
                "insight_goal": "What business insight this question aims to uncover",
                "priority": "high|medium|low"
            }}
        ]

        Focus on questions that would be genuinely useful for understanding the data and making decisions.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            content = response.choices[0].message.content.strip()

            # Clean up response
            content = clean_markdown_code_blocks(content, 'json')
            
            try:
                questions = json.loads(content)
                
                # Validate and enrich questions
                validated_questions = []
                for i, q in enumerate(questions):
                    if self._validate_question(q):
                        q['id'] = i + 1
                        q['generated_at'] = 'auto'
                        validated_questions.append(q)
                
                print(f"Generated {len(validated_questions)} valid questions")
                return validated_questions
                
            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {e}")
                print(f"Raw response: {content[:500]}...")
                return self._generate_fallback_questions()
                
        except Exception as e:
            print(f"Error generating questions: {e}")
            return self._generate_fallback_questions()
    
    def _validate_question(self, question_dict: Dict) -> bool:
        """
        Validate question has all required fields
        """
        required_fields = ['question', 'chart_type', 'analysis_type']
        return all(field in question_dict for field in required_fields)
    
    def _generate_fallback_questions(self) -> List[Dict[str, Any]]:
        """
        Fallback questions if AI generation failed - specific for SQL Murder Mystery database
        """
        return [
            {
                "id": 1,
                "question": "Show me the distribution of people by hair color from drivers license",
                "chart_type": "bar",
                "analysis_type": "distribution",
                "insight_goal": "Understand hair color distribution among drivers",
                "priority": "high",
                "generated_at": "fallback"
            },
            {
                "id": 2,
                "question": "What is the age distribution of drivers",
                "chart_type": "histogram",
                "analysis_type": "distribution", 
                "insight_goal": "Analyze age patterns in drivers license data",
                "priority": "high",
                "generated_at": "fallback"
            },
            {
                "id": 3,
                "question": "Compare the number of people by gender from drivers license",
                "chart_type": "bar",
                "analysis_type": "comparison",
                "insight_goal": "Compare gender distribution",
                "priority": "high", 
                "generated_at": "fallback"
            },
            {
                "id": 4,
                "question": "Show me eye color distribution",
                "chart_type": "pie",
                "analysis_type": "distribution",
                "insight_goal": "Understand eye color patterns",
                "priority": "medium",
                "generated_at": "fallback"
            }
        ]
    
    def generate_questions_from_patterns(self,
                                       data_patterns: Dict[str, Any],
                                       user_intent: str = "Analyze the data") -> List[Dict[str, Any]]:
        """
        Generate questions based on detected data patterns
        """
        questions = []
        question_id = 1
        
        for table_name, patterns in data_patterns.items():
            for pattern in patterns:
                if pattern['type'] == 'distribution':
                    for col in pattern['columns']:
                        questions.append({
                            "id": question_id,
                            "question": f"What is the distribution of {col} in {table_name}?",
                            "chart_type": "histogram",
                            "tables_involved": [table_name],
                            "columns_involved": [col],
                            "analysis_type": "distribution",
                            "insight_goal": f"Understand the distribution pattern of {col}",
                            "priority": "high",
                            "generated_at": "pattern_based"
                        })
                        question_id += 1
                
                elif pattern['type'] == 'categorical_breakdown':
                    for col in pattern['columns']:
                        questions.append({
                            "id": question_id,
                            "question": f"Show the breakdown by {col} in {table_name}",
                            "chart_type": "pie",
                            "tables_involved": [table_name],
                            "columns_involved": [col],
                            "analysis_type": "breakdown", 
                            "insight_goal": f"Understand category distribution for {col}",
                            "priority": "high",
                            "generated_at": "pattern_based"
                        })
                        question_id += 1
                
                elif pattern['type'] == 'correlation' and len(pattern['columns']) >= 2:
                    col1, col2 = pattern['columns'][:2]
                    questions.append({
                        "id": question_id,
                        "question": f"What is the relationship between {col1} and {col2} in {table_name}?",
                        "chart_type": "scatter",
                        "tables_involved": [table_name],
                        "columns_involved": [col1, col2],
                        "analysis_type": "correlation",
                        "insight_goal": f"Discover correlation patterns between {col1} and {col2}",
                        "priority": "medium",
                        "generated_at": "pattern_based"
                    })
                    question_id += 1
                
                elif pattern['type'] == 'cross_analysis':
                    if pattern['numeric_columns'] and pattern['categorical_columns']:
                        num_col = pattern['numeric_columns'][0]
                        cat_col = pattern['categorical_columns'][0]
                        questions.append({
                            "id": question_id,
                            "question": f"How does {num_col} vary across different {cat_col} in {table_name}?",
                            "chart_type": "box",
                            "tables_involved": [table_name],
                            "columns_involved": [num_col, cat_col],
                            "analysis_type": "comparison",
                            "insight_goal": f"Compare {num_col} distribution across {cat_col} categories",
                            "priority": "medium",
                            "generated_at": "pattern_based"
                        })
                        question_id += 1

        # Limit number of questions
        return questions[:8]  # Maximum 8 questions
    
    def prioritize_questions(self, questions: List[Dict[str, Any]],
                           max_questions: int = 5) -> List[Dict[str, Any]]:
        """
        Prioritize and filter questions based on priority and diversity
        """
        # Sort by priority
        priority_order = {'high': 3, 'medium': 2, 'low': 1}
        questions.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 1), reverse=True)
        
        # Ensure diversity in chart types
        selected_questions = []
        used_chart_types = set()
        
        for q in questions:
            if len(selected_questions) >= max_questions:
                break
                
            chart_type = q.get('chart_type')

            # Prioritize different chart types
            if chart_type not in used_chart_types or len(selected_questions) < max_questions // 2:
                selected_questions.append(q)
                used_chart_types.add(chart_type)

        # If not enough, add remaining questions
        for q in questions:
            if len(selected_questions) >= max_questions:
                break
            if q not in selected_questions:
                selected_questions.append(q)
        
        # Update IDs
        for i, q in enumerate(selected_questions):
            q['id'] = i + 1
            
        return selected_questions


if __name__ == "__main__":
    # Test with mock data
    pass