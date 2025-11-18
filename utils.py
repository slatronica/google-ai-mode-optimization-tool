"""Utility functions for WordPress SEO analyzer"""
import re
import logging

logger = logging.getLogger(__name__)


def clean_html(html: str) -> str:
    """Remove HTML tags and clean text"""
    text = re.sub('<.*?>', '', html)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

