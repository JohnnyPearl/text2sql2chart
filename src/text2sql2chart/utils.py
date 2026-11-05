"""
Utility functions for the text2sql2chart project.
This module contains shared utilities to reduce code duplication.
"""

import os
import pandas as pd
from typing import Optional, Tuple, Any


GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


def _get_model_for_provider(provider: str) -> str:
    """
    Resolve model from environment with provider-specific defaults.

    Priority:
    - openai: OPENAI_MODEL -> gpt-4o-mini
    - gemini: gemini-2.0-flash
    """
    if provider == "openai":
        return os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    return DEFAULT_GEMINI_MODEL


def get_ai_provider_config() -> Tuple[str, str, str]:
    """
    Read AI provider configuration from environment variables.

    Returns:
        Tuple of (provider, api_key, model).
        provider is 'gemini' or 'openai'.

    Raises:
        ValueError: If required API key environment variable is not set.
    """
    provider = os.getenv("AI_PROVIDER", "openai").lower()
    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable not set. "
                "Please set it or use AI_PROVIDER=openai with OPENAI_API_KEY."
            )
        return provider, api_key, _get_model_for_provider("gemini")
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable not set. "
                "Please set it or use AI_PROVIDER=gemini with GEMINI_API_KEY."
            )
        return "openai", api_key, _get_model_for_provider("openai")


def create_openai_compatible_client(api_key: str, provider: str = "openai"):
    """
    Create an OpenAI-compatible client for the given provider.

    For 'gemini', uses Google's OpenAI-compatible endpoint.
    For 'openai', uses the standard OpenAI endpoint.

    Args:
        api_key: API key for the provider.
        provider: 'gemini' or 'openai'.

    Returns:
        Tuple of (OpenAI client, model name string).
    """
    from openai import OpenAI

    if provider == "gemini":
        client = OpenAI(api_key=api_key, base_url=GEMINI_BASE_URL)
        return client, _get_model_for_provider("gemini")
    else:
        client = OpenAI(api_key=api_key)
        return client, _get_model_for_provider("openai")


def clean_markdown_code_blocks(text: str, block_type: str = 'json') -> str:
    """
    Remove markdown code block delimiters from text.

    Args:
        text: Text that may contain markdown code blocks
        block_type: Type of code block (e.g., 'json', 'python')

    Returns:
        Cleaned text without markdown delimiters
    """
    content = text.strip()

    # Remove language-specific code block markers
    if block_type and content.startswith(f'```{block_type}'):
        content = content[3 + len(block_type):]

    # Remove generic code block markers
    if content.startswith('```'):
        content = content[3:]
    if content.endswith('```'):
        content = content[:-3]

    return content.strip()


def parse_vanna_result(result: Any) -> Tuple[Optional[str], Optional[pd.DataFrame]]:
    """
    Parse various Vanna result formats and extract SQL query and DataFrame.

    Vanna can return results in multiple formats:
    - Tuple: (sql_query, dataframe)
    - DataFrame directly
    - Object with .df attribute
    - Dict with 'df' key

    Args:
        result: Result from Vanna query execution

    Returns:
        Tuple of (sql_query, dataframe). Either may be None if not found.
    """
    sql_query = None
    df = None

    # Check if result is a tuple (sql_query, df)
    if isinstance(result, tuple) and len(result) >= 2:
        sql_query = result[0] if isinstance(result[0], str) else None
        df = result[1] if hasattr(result[1], 'shape') else None
    # Check if result is a DataFrame directly
    elif hasattr(result, 'shape') and hasattr(result, 'columns'):
        df = result
    # Check if result has a df attribute
    elif hasattr(result, 'df') and result.df is not None:
        df = result.df
        if hasattr(result, 'sql'):
            sql_query = result.sql
    # Check if result is a dict with 'df' key
    elif isinstance(result, dict):
        if 'df' in result:
            df = result['df']
        if 'sql' in result:
            sql_query = result['sql']

    return sql_query, df


def validate_dataframe(df: Optional[pd.DataFrame], context: str = "query") -> bool:
    """
    Check if a DataFrame is valid (not None and not empty).

    Args:
        df: DataFrame to validate
        context: Context string for error message

    Returns:
        True if DataFrame is valid, False otherwise
    """
    if df is None:
        print(f"No data returned from {context}")
        return False

    if df.empty:
        print(f"Empty DataFrame returned from {context}")
        return False

    return True
