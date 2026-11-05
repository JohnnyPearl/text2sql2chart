"""
Query Transformer Module
Normalize and optimize user query before processing

3 methods:
1. Query Rewriting - Rewrite query more clearly
2. Step Back Prompting - Create more general questions
3. Subquery Decomposition - Break down complex questions
"""
from typing import Dict, List, Any, Optional
import json
import math

from text2sql2chart.utils import create_openai_compatible_client


class QueryTransformer:
    """
    Transform and normalize user query before processing
    """

    def __init__(self, api_key: str, model: str = None, provider: str = "openai"):
        """
        Initialize Query Transformer

        Args:
            api_key: API key for the AI provider
            model: Model name to use (defaults to provider default)
            provider: 'openai' or 'gemini'
        """
        self.client, default_model = create_openai_compatible_client(api_key, provider)
        self.model = model if model is not None else default_model
    
    def transform_query(self, 
                       user_query: str,
                       method: str = "rewriting",
                       database_schema: Optional[str] = None) -> Dict[str, Any]:
        """
        Transform query using specified method
        
        Args:
            user_query: Original user query
            method: Transformation method - "rewriting", "step_back", "decomposition"
            database_schema: Database schema info (optional)
        
        Returns:
            Dict containing transformed query and metadata
        """
        
        if method == "rewriting":
            return self._query_rewriting(user_query, database_schema)
        elif method == "step_back":
            return self._step_back_prompting(user_query, database_schema)
        elif method == "decomposition":
            return self._subquery_decomposition(user_query, database_schema)
        else:
            raise ValueError(f"Unknown method: {method}. Use 'rewriting', 'step_back', or 'decomposition'")
    
    def _query_rewriting(self, user_query: str, database_schema: Optional[str] = None) -> Dict[str, Any]:
        """
        Query Rewriting: Rewrite query more clearly and specifically

        Example:
        - Input: "Show me data"
        - Output: "Show me all records from the main table with their key attributes"
        """
        
        schema_context = f"\n\nDatabase Schema:\n{database_schema}" if database_schema else ""
        
        prompt = f"""You are a query optimization expert. Your task is to REWRITE the user's vague or unclear query into a CLEAR, SPECIFIC, and ACTIONABLE query.

Guidelines:
- Make the query more specific and concrete
- Add relevant context if missing
- Clarify ambiguous terms
- Keep the same intent but make it clearer
- If query is already clear, improve it slightly

Original Query: "{user_query}"{schema_context}

Provide your response in JSON format:
{{
    "rewritten_query": "The rewritten, clearer version of the query",
    "improvements": ["List of improvements made"],
    "confidence": 0.0-1.0
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at rewriting queries to be clearer and more specific."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return {
                "method": "query_rewriting",
                "original_query": user_query,
                "transformed_query": result.get("rewritten_query", user_query),
                "metadata": {
                    "improvements": result.get("improvements", []),
                    "confidence": result.get("confidence", 0.8)
                },
                "success": True
            }
            
        except Exception as e:
            print(f"Error in query rewriting: {e}")
            return {
                "method": "query_rewriting",
                "original_query": user_query,
                "transformed_query": user_query,
                "metadata": {"error": str(e)},
                "success": False
            }
    
    def _step_back_prompting(self, user_query: str, database_schema: Optional[str] = None) -> Dict[str, Any]:
        """
        Step Back Prompting: Create more general questions to understand broader context

        Example:
        - Input: "What's the average salary of engineers in San Francisco?"
        - Step Back: "What factors affect salary distribution across different job roles and locations?"
        """
        
        schema_context = f"\n\nDatabase Schema:\n{database_schema}" if database_schema else ""
        
        prompt = f"""You are a strategic thinking expert. Your task is to create a STEP BACK question that is more GENERAL and ABSTRACT than the specific query.

The step back question should:
- Be broader in scope
- Focus on underlying principles or patterns
- Help understand the bigger picture
- Guide better analysis

Original Query: "{user_query}"{schema_context}

Provide your response in JSON format:
{{
    "step_back_query": "A broader, more general version of the query",
    "original_aspects": ["Specific aspects from original query"],
    "broader_aspects": ["Broader aspects to consider"],
    "reasoning": "Why this step back helps"
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at creating step-back questions to understand broader context."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return {
                "method": "step_back_prompting",
                "original_query": user_query,
                "transformed_query": result.get("step_back_query", user_query),
                "metadata": {
                    "original_aspects": result.get("original_aspects", []),
                    "broader_aspects": result.get("broader_aspects", []),
                    "reasoning": result.get("reasoning", "")
                },
                "success": True
            }
            
        except Exception as e:
            print(f"Error in step back prompting: {e}")
            return {
                "method": "step_back_prompting",
                "original_query": user_query,
                "transformed_query": user_query,
                "metadata": {"error": str(e)},
                "success": False
            }
    
    def _subquery_decomposition(self, user_query: str, database_schema: Optional[str] = None) -> Dict[str, Any]:
        """
        Subquery Decomposition: Break down complex questions into simple sub-questions

        Example:
        - Input: "Compare sales trends between regions and show top products"
        - Subqueries:
            1. "What are the sales by region?"
            2. "What is the trend over time for each region?"
            3. "What are the top-selling products?"
        """
        
        schema_context = f"\n\nDatabase Schema:\n{database_schema}" if database_schema else ""
        
        prompt = f"""You are a query decomposition expert. Your task is to BREAK DOWN a complex query into SIMPLER, INDEPENDENT subqueries.

Guidelines:
- Identify multiple aspects or questions within the original query
- Create simple, focused subqueries
- Each subquery should be independently answerable
- Maintain logical order if there are dependencies
- If query is already simple, still create 1-2 subqueries

Original Query: "{user_query}"{schema_context}

Provide your response in JSON format:
{{
    "is_complex": true/false,
    "subqueries": [
        {{
            "order": 1,
            "subquery": "First simple question",
            "purpose": "What this answers",
            "dependencies": []
        }},
        ...
    ],
    "synthesis_hint": "How to combine results from subqueries"
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at decomposing complex queries into simpler subqueries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            subqueries = result.get("subqueries", [])
            subquery_texts = [sq.get("subquery", "") for sq in subqueries]
            
            return {
                "method": "subquery_decomposition",
                "original_query": user_query,
                "transformed_query": user_query,  # Keep original as main
                "subqueries": subquery_texts,
                "metadata": {
                    "is_complex": result.get("is_complex", False),
                    "subquery_details": subqueries,
                    "synthesis_hint": result.get("synthesis_hint", ""),
                    "num_subqueries": len(subqueries)
                },
                "success": True
            }
            
        except Exception as e:
            print(f"Error in subquery decomposition: {e}")
            return {
                "method": "subquery_decomposition",
                "original_query": user_query,
                "transformed_query": user_query,
                "subqueries": [user_query],
                "metadata": {"error": str(e)},
                "success": False
            }
    
    def transform_and_compare(self, 
                             user_query: str,
                             database_schema: Optional[str] = None) -> Dict[str, Any]:
        """
        Apply all three transformation methods and compare results
        
        Returns:
            Dict with all three transformations and recommendations
        """
        
        print(f"Transforming query: '{user_query}'")
        print("-" * 60)
        
        # Apply all methods
        rewriting = self._query_rewriting(user_query, database_schema)
        step_back = self._step_back_prompting(user_query, database_schema)
        decomposition = self._subquery_decomposition(user_query, database_schema)
        
        # Display results
        print("\n1. QUERY REWRITING:")
        print(f"   Original: {user_query}")
        print(f"   Rewritten: {rewriting['transformed_query']}")
        if rewriting.get('metadata', {}).get('improvements'):
            print(f"   Improvements: {', '.join(rewriting['metadata']['improvements'])}")
        
        print("\n2. STEP BACK PROMPTING:")
        print(f"   Original: {user_query}")
        print(f"   Step Back: {step_back['transformed_query']}")
        if step_back.get('metadata', {}).get('reasoning'):
            print(f"   Reasoning: {step_back['metadata']['reasoning']}")
        
        print("\n3. SUBQUERY DECOMPOSITION:")
        print(f"   Original: {user_query}")
        if decomposition.get('subqueries'):
            for i, sq in enumerate(decomposition['subqueries'], 1):
                print(f"   Subquery {i}: {sq}")
        
        return {
            "original_query": user_query,
            "transformations": {
                "rewriting": rewriting,
                "step_back": step_back,
                "decomposition": decomposition
            },
            "recommendations": self._get_recommendations(rewriting, step_back, decomposition)
        }
    
    def _get_recommendations(self, rewriting, step_back, decomposition) -> Dict[str, Any]:
        """Generate recommendations on which method to use"""
        
        recommendations = {
            "best_for_specific_query": "rewriting",
            "best_for_exploration": "step_back", 
            "best_for_complex_query": "decomposition"
        }
        
        # Determine if query is complex
        is_complex = decomposition.get('metadata', {}).get('is_complex', False)
        num_subqueries = decomposition.get('metadata', {}).get('num_subqueries', 1)
        
        if num_subqueries > 2:
            recommendations["primary_method"] = "decomposition"
            recommendations["reason"] = "Query is complex with multiple aspects"
        elif rewriting.get('metadata', {}).get('confidence', 0) > 0.8:
            recommendations["primary_method"] = "rewriting"
            recommendations["reason"] = "Query can be effectively clarified through rewriting"
        else:
            recommendations["primary_method"] = "step_back"
            recommendations["reason"] = "Broader context will help understanding"
        
        return recommendations

    # ========= New: Similarity-based ranking across methods =========
    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """Compute cosine similarity between two vectors without numpy"""
        dot = sum(a * b for a, b in zip(v1, v2))
        n1 = math.sqrt(sum(a * a for a in v1)) or 1e-8
        n2 = math.sqrt(sum(b * b for b in v2)) or 1e-8
        return dot / (n1 * n2)

    def rank_by_similarity(self,
                           user_query: str,
                           database_schema: Optional[str] = None,
                           embedding_model: str = "text-embedding-3-small") -> Dict[str, Any]:
        """
        Apply all methods, rank transformed queries by semantic similarity to the original, and pick the closest.

        Returns:
            {
              'method': 'rank_by_similarity',
              'original_query': str,
              'transformed_query': str,   # selected text
              'selected': { 'method': str, 'text': str, 'score': float },
              'ranking': [ { 'method': str, 'text': str, 'score': float } ... ],
              'components': { 'rewriting': {...}, 'step_back': {...}, 'decomposition': {...} },
              'success': True/False
            }
        """

        try:
            # Run the three transformations
            rewriting = self._query_rewriting(user_query, database_schema)
            step_back = self._step_back_prompting(user_query, database_schema)
            decomposition = self._subquery_decomposition(user_query, database_schema)

            # Build candidate texts
            candidates: List[Dict[str, Any]] = []

            if rewriting.get('success'):
                candidates.append({
                    'method': 'rewriting',
                    'text': rewriting.get('transformed_query', user_query)
                })

            if step_back.get('success'):
                candidates.append({
                    'method': 'step_back',
                    'text': step_back.get('transformed_query', user_query)
                })

            # For decomposition, evaluate each subquery; pick the most similar subquery
            if decomposition.get('success'):
                subqueries = decomposition.get('subqueries', []) or [user_query]
                # Limit very large lists just in case
                subqueries = subqueries[:10]
            else:
                subqueries = [user_query]

            # Create embedding inputs: original + all candidates including subqueries
            embedding_inputs: List[str] = [user_query]
            embedding_map: List[Dict[str, Any]] = []  # keeps order and mapping to candidate entries

            # Add rewriting and step_back first
            for c in candidates:
                embedding_inputs.append(c['text'])
                embedding_map.append({ 'method': c['method'], 'text': c['text'] })

            # Add decomposition subqueries as separate candidates to measure similarity individually
            for sq in subqueries:
                embedding_inputs.append(sq)
                embedding_map.append({ 'method': 'decomposition', 'text': sq })

            # Generate embeddings
            emb_resp = self.client.embeddings.create(model=embedding_model, input=embedding_inputs)
            vectors = [d.embedding for d in emb_resp.data]

            original_vec = vectors[0]
            candidate_vecs = vectors[1:]

            # Compute similarities
            scored: List[Dict[str, Any]] = []
            for meta, vec in zip(embedding_map, candidate_vecs):
                score = self._cosine_similarity(original_vec, vec)
                scored.append({ 'method': meta['method'], 'text': meta['text'], 'score': float(score) })

            # Consolidate: for decomposition we may have multiple subquery entries; take the best
            best_by_method: Dict[str, Dict[str, Any]] = {}
            for item in scored:
                m = item['method']
                if (m not in best_by_method) or (item['score'] > best_by_method[m]['score']):
                    best_by_method[m] = item

            # Build final ranking list with one entry per method
            ranking = sorted(best_by_method.values(), key=lambda x: x['score'], reverse=True)
            selected = ranking[0] if ranking else { 'method': 'rewriting', 'text': user_query, 'score': 0.0 }

            return {
                'method': 'rank_by_similarity',
                'original_query': user_query,
                'transformed_query': selected['text'],
                'selected': selected,
                'ranking': ranking,
                'components': {
                    'rewriting': rewriting,
                    'step_back': step_back,
                    'decomposition': decomposition
                },
                'success': True
            }

        except Exception as e:
            print(f"Error in rank_by_similarity: {e}")
            return {
                'method': 'rank_by_similarity',
                'original_query': user_query,
                'transformed_query': user_query,
                'selected': {'method': 'original', 'text': user_query, 'score': 0.0},
                'ranking': [],
                'components': {},
                'success': False,
                'error': str(e)
            }


def demo_query_transformer():
    """Demo function to showcase query transformation"""
    
    import os
    
    # You'll need to set your API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set.")
    
    transformer = QueryTransformer(api_key)
    
    # Test queries
    test_queries = [
        "Show me the data",
        "Phân tích database này",
        "Compare performance across regions and identify top products",
        "What's happening with sales?",
        "Create smart charts for data"
    ]
    
    for query in test_queries:
        print("\n" + "=" * 80)
        result = transformer.transform_and_compare(query)
        print("\nRECOMMENDATION:")
        print(f"   Primary Method: {result['recommendations']['primary_method']}")
        print(f"   Reason: {result['recommendations']['reason']}")
        print("=" * 80)


if __name__ == "__main__":
    demo_query_transformer()
