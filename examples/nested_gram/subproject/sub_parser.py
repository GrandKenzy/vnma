"""Subproject module that imports and uses Gram."""

import gram


def analyze_with_gram(code_snippet: str) -> dict:
    """Demonstrate calling Gram APIs from an intermediate dependency."""
    # Gram module check
    return {
        "status": "success",
        "gram_module": gram.__name__,
        "gram_file": getattr(gram, "__file__", "unknown"),
        "input_snippet": code_snippet,
    }
