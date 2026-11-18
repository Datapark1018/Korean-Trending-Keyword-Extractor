"""Emerging keywords from Korean post titles."""

from .config import TrendConfig
from .core import analyze_posts, trending_keywords

__all__ = ["TrendConfig", "analyze_posts", "trending_keywords"]
__version__ = "0.1.0"
