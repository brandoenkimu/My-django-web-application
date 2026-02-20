# templatetags/bio_filters.py
from django import template
import re

register = template.Library()


@register.filter
def split_tags(text):
    """Split bio text into tags by common delimiters"""
    if not text:
        return []

    # Split by commas, periods, spaces, and newlines
    words = re.split(r'[,\s\.\n]+', text)

    # Filter out empty strings and common words
    common_words = ['the', 'and', 'you', 'for', 'are', 'that', 'with', 'this', 'have', 'from', 'they', 'would']

    tags = []
    for word in words:
        word = word.strip().lower()
        if (len(word) >= 3 and
                word not in common_words and
                word not in tags and
                not word.isdigit()):
            tags.append(word.title())

    return tags[:10]  # Return only first 10 tags


@register.filter
def extract_keywords(text):
    """Extract keywords from bio text"""
    if not text:
        return []

    # Common trading and professional keywords to look for
    trading_keywords = [
        'trader', 'trading', 'investor', 'investment', 'forex', 'stocks',
        'crypto', 'cryptocurrency', 'algorithmic', 'technical', 'fundamental',
        'analysis', 'analyst', 'swing', 'day', 'position', 'scalper', 'scalping',
        'options', 'futures', 'commodities', 'indices', 'market', 'markets',
        'profit', 'loss', 'risk', 'management', 'strategy', 'strategies',
        'portfolio', 'diversification', 'volatility', 'liquidity', 'margin',
        'leverage', 'hedge', 'hedging', 'arbitrage', 'speculation', 'speculative'
    ]

    found_keywords = []
    text_lower = text.lower()

    for keyword in trading_keywords:
        if keyword in text_lower:
            found_keywords.append(keyword.title())

    # If no specific keywords found, use split_tags
    if not found_keywords:
        found_keywords = split_tags(text)

    return found_keywords[:5]


@register.filter
def linebreaks_keep(text):
    """Convert newlines to <br> tags but keep template safe"""
    from django.utils.safestring import mark_safe
    if not text:
        return ''
    return mark_safe(text.replace('\n', '<br>'))