import logging
import re
import time
from datetime import timedelta
from html.parser import HTMLParser

import requests
from django.conf import settings
from django.utils import timezone
from google import genai

logger = logging.getLogger(__name__)

from ..models import CachedArticle
from .news_api import fetch_news

CACHE_DURATION = timedelta(minutes=30)


class ArticleTextParser(HTMLParser):
    """Collect readable text while ignoring page chrome and embedded code."""

    ignored_tags = {'script', 'style', 'noscript', 'svg', 'nav', 'footer', 'header'}

    def __init__(self):
        super().__init__()
        self.parts = []
        self.ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.ignored_tags:
            self.ignored_depth += 1

    def handle_endtag(self, tag):
        if tag in self.ignored_tags and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data):
        if not self.ignored_depth:
            text = ' '.join(data.split())
            if text:
                self.parts.append(text)


def extract_article_text(url):
    if not url or not url.startswith(('http://', 'https://')):
        return ''
    try:
        response = requests.get(
            url,
            headers={'User-Agent': 'NewsMind/1.0 article summarizer'},
            timeout=8,
        )
        response.raise_for_status()
        parser = ArticleTextParser()
        parser.feed(response.text)
        return ' '.join(parser.parts)
    except (requests.RequestException, ValueError):
        return ''


def summarize_article(url, description=''):
    article_text = extract_article_text(url)
    summary = summarize(article_text)
    if summary:
        return summary, False
    return summarize(description), True


def summarize(text):
    if not text:
        return ''
    sentences = [sentence.strip() for sentence in re.split(r'(?<=[.!?])\s+', text) if sentence.strip()]
    return ' '.join(sentences[:3])


def _clean_summary_text(value):
    if not isinstance(value, str):
        return ''
    cleaned = ' '.join(value.split())
    return cleaned.strip()


def _is_retryable_gemini_error(exc):
    message = str(exc).lower()
    error_type = type(exc).__name__.lower()
    return '503' in message or 'unavailable' in message or 'temporarily' in message or 'retry' in message or 'timeout' in message or error_type in {'servererror', 'serviceunavailable'}


def generate_gemini_summary(content=''):
    text = (content or '').strip()
    if not text:
        logger.warning('Gemini summarization skipped: empty content payload.')
        return '', False

    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    if not api_key:
        logger.warning('Gemini summarization skipped: GEMINI_API_KEY is missing or empty.')
        return '', False

    prompt = (
        "Write a concise, informative summary of the supplied article content in exactly 3 or 4 complete sentences as one standalone paragraph. "
        "Explain what happened, identify who or what is involved, and include the most important supporting facts and relevant context that are explicitly present. "
        "Combine related facts and remove repetition or secondary details instead of mechanically paraphrasing each source sentence. "
        "Use clear, natural language and preserve important factual information. "
        "Do not invent facts, add opinions, or add information not present in the supplied content. "
        "Do not use bullet points, headings, or the prefixes 'Summary:' or 'AI Summary:'. Return only the summary paragraph.\n\n"
        f"{text[:12000]}"
    )

    for attempt in range(2):
        try:
            client = genai.Client(api_key=api_key)

            try:
                response = client.models.generate_content(
                    model='gemini-3.6-flash',
                    contents=prompt,
                )
                text_value = getattr(response, 'text', None)
                if text_value:
                    return _clean_summary_text(text_value), False

                candidates = getattr(response, 'candidates', None)
                if candidates:
                    first = candidates[0]
                    content_obj = getattr(first, 'content', None)
                    parts = getattr(content_obj, 'parts', []) if content_obj else []
                    combined_text = ' '.join(
                        part.text for part in parts if getattr(part, 'text', None)
                    )
                    cleaned = _clean_summary_text(combined_text)
                    if cleaned:
                        return cleaned, False

                logger.warning('Gemini returned an empty or unparseable response payload.')
                return '', False
            except Exception as exc:
                if _is_retryable_gemini_error(exc) and attempt == 0:
                    logger.warning('Gemini transient failure on attempt %s: %s: %s', attempt + 1, type(exc).__name__, exc)
                    time.sleep(1)
                    continue
                logger.warning('Gemini SDK call failed: %s: %s', type(exc).__name__, exc)
                return '', _is_retryable_gemini_error(exc)
        except Exception as exc:
            if _is_retryable_gemini_error(exc) and attempt == 0:
                logger.warning('Gemini client initialization transient failure on attempt %s: %s: %s', attempt + 1, type(exc).__name__, exc)
                time.sleep(1)
                continue
            logger.warning('Gemini client initialization failed: %s: %s', type(exc).__name__, exc)
            return '', _is_retryable_gemini_error(exc)

    return '', False


def key_points(text):
    if not text:
        return []
    sentences = [sentence.strip() for sentence in re.split(r'(?<=[.!?])\s+', text) if sentence.strip()]
    return sentences[:4]


def _cached_article_to_raw_article(article):
    fallback_text = article.headline or ''
    return {
        'title': article.headline,
        'source': {'name': article.source},
        'publishedAt': article.fetched_at.isoformat(),
        'urlToImage': '',
        'description': fallback_text,
        'summary': fallback_text,
        'summary_fallback': bool(not fallback_text),
        'key_points': key_points(fallback_text),
        'url': article.original_url,
        'valid_url': True,
    }


def get_cached_articles(category='general'):
    category_name = (category or 'general').strip() or 'general'
    cutoff = timezone.now() - CACHE_DURATION
    cached_articles = CachedArticle.objects.filter(
        category=category_name,
        fetched_at__gt=cutoff,
    ).order_by('-fetched_at')[:20]
    return [_cached_article_to_raw_article(article) for article in cached_articles]


def save_article_to_cache(headline, source, original_url, category, summary):
    if not headline:
        return None
    category_name = (category or 'general').strip() or 'general'
    cache_entry, _ = CachedArticle.objects.get_or_create(
        original_url=original_url,
        defaults={
            'headline': headline[:500],
            'source': source[:200],
            'category': category_name,
        },
    )
    cache_entry.headline = headline[:500]
    cache_entry.source = source[:200]
    cache_entry.category = category_name
    cache_entry.save(update_fields=['headline', 'source', 'category'])
    return cache_entry


def get_articles_for_category(category, page=1, page_size=20):
    category_name = (category or 'general').strip() or 'general'
    cached_articles = get_cached_articles(category_name)
    if cached_articles:
        return cached_articles

    try:
        raw_articles = fetch_news(category_name, page=page, page_size=page_size)
    except Exception:
        raw_articles = []

    if not raw_articles:
        return []

    processed_articles = []
    for article in raw_articles:
        title = article.get('title', '')
        description = article.get('description', '')
        source = article.get('source', {}).get('name', 'NewsMind')
        url = article.get('url', '')

        summary = summarize(description) if description else ''
        if not summary and title:
            summary = title

        try:
            save_article_to_cache(title, source, url, category_name, summary)
        except Exception:
            pass

        article_copy = dict(article)
        article_copy['description'] = summary or description
        article_copy['summary'] = summary or description
        article_copy['summary_fallback'] = bool(not summary)
        article_copy['key_points'] = key_points(summary or description)
        article_copy['valid_url'] = bool(url and url.startswith(('http://', 'https://')))
        processed_articles.append(article_copy)

    return processed_articles
