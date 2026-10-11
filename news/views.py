import json
import logging
import random
import time
from urllib.parse import urlparse

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

logger = logging.getLogger(__name__)

from .models import CachedArticle
from .services.news_api import fetch_news
from .services.summarizer import (
    extract_article_text,
    generate_gemini_summary,
    get_articles_for_category,
    key_points,
)


TOPICS = [
    "technology",
    "sports",
    "india",
    "world",
    "business",
    "science",
    "entertainment",
]

HOME_FEED_CACHE_KEY = "newsmind:home-feed:v1"
HOME_FEED_STALE_CACHE_KEY = "newsmind:home-feed-stale:v1"
HOME_FEED_TIMEOUT = 15 * 60
HOME_FEED_STALE_TIMEOUT = 24 * 60 * 60


def get_home_raw_articles():
    raw_articles = cache.get(HOME_FEED_CACHE_KEY)
    if raw_articles:
        return raw_articles, False

    fetched_articles = []
    for topic in TOPICS[:2]:
        started_at = time.perf_counter()
        topic_articles = []
        try:
            topic_articles = fetch_news(topic, page=1, page_size=8)
            fetched_articles.extend(topic_articles)
        except Exception:
            logger.exception("News feed request failed for topic %s", topic)
        elapsed = time.perf_counter() - started_at
        logger.info(
            "Fetched %d articles for topic %s in %.2f seconds",
            len(topic_articles),
            topic,
            elapsed,
        )

    if fetched_articles:
        random.shuffle(fetched_articles)
        cache.set(HOME_FEED_CACHE_KEY, fetched_articles, HOME_FEED_TIMEOUT)
        cache.set(
            HOME_FEED_STALE_CACHE_KEY,
            fetched_articles,
            HOME_FEED_STALE_TIMEOUT,
        )
        return fetched_articles, False

    return cache.get(HOME_FEED_STALE_CACHE_KEY) or [], True


def prepare_articles(raw_articles):

    articles = []

    for i, article in enumerate(raw_articles):

        description = article.get("description", "")

        # Skip articles with no title or removed content
        title = article.get("title", "")
        if not title or title == "[Removed]":
            continue

        image_url = article.get("urlToImage", "")
        url = article.get("url", "")

        articles.append({
            "id": i,
            "title": title,
            "source": article.get("source", {}).get("name", ""),
            "date": article.get("publishedAt", "")[:10],

            # Only store image if it's a real http/https URL
            "image": (
                image_url
                if image_url and image_url.startswith("http")
                else ""
            ),

            "summary": description or "Summary unavailable for this article.",

            "summary_fallback": not bool(description),

            "key_points": key_points(description),

            "url": url,

            "valid_url": urlparse(url).scheme in ("http", "https"),

            "description": description,
        })

    return articles


def home(request):

    query = request.GET.get("q", "")

    try:
        page = int(request.GET.get("page", 1))
    except ValueError:
        page = 1

    if page < 1:
        page = 1

    loading_feed = False

    if not query:
        raw_articles, _ = get_home_raw_articles()
        loading_feed = not bool(raw_articles)

    else:

        try:
            raw_articles = get_articles_for_category(
                query,
                page=page,
                page_size=20
            )
        except Exception:
            raw_articles = []

    articles = prepare_articles(raw_articles)

    return render(
        request,
        "news/home.html",
        {
            "articles": articles,
            "query": query,
            "topics": TOPICS,
            "page": page,
            "feed_loading": loading_feed,
        }
    )


@require_GET
def home_feed(request):
    raw_articles, _ = get_home_raw_articles()

    articles = prepare_articles(raw_articles)
    html = render_to_string(
        "news/article_cards.html",
        {"articles": articles, "query": "", "request": request},
        request=request,
    )
    return JsonResponse({"html": html, "count": len(articles)})


@require_POST
@csrf_protect
def summarize_article(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "error": "Invalid request payload."}, status=400)

    url = (payload.get("url") or "").strip()
    title = (payload.get("title") or "").strip()
    description = (payload.get("description") or "").strip()
    source = (payload.get("source") or "NewsMind").strip() or "NewsMind"
    category = (payload.get("category") or "general").strip() or "general"

    if not url:
        return JsonResponse({"success": False, "error": "Missing article URL."}, status=400)

    article, created = CachedArticle.objects.get_or_create(
        original_url=url,
        defaults={
            "headline": (title or "Untitled article")[:500],
            "source": source[:200],
            "category": category[:100],
        },
    )

    if article.ai_summary:
        return JsonResponse({"success": True, "summary": article.ai_summary, "cached": True})

    if len(description) >= 120:
        extracted_text = ""
        content = description
    else:
        extracted_text = extract_article_text(url)
        content = (extracted_text or description or "").strip()

    if not content or len(content) < 30:
        return JsonResponse({"success": False, "error": "Not enough article information is available to generate a summary."}, status=400)

    try:
        summary, temporary_unavailable = generate_gemini_summary(content)
    except Exception:
        return JsonResponse({"success": False, "error": "AI service is temporarily unavailable. Please try again."}, status=503)

    if not summary:
        logger.warning(
            'Gemini summary generation failed for article URL=%s, extracted_length=%s, description_length=%s',
            url,
            len(extracted_text) if extracted_text else 0,
            len(description) if description else 0,
        )
        if temporary_unavailable:
            return JsonResponse({"success": False, "error": "AI service is temporarily unavailable. Please try again."}, status=503)
        return JsonResponse({"success": False, "error": "AI summary could not be generated."}, status=400)

    article.ai_summary = summary
    article.save(update_fields=["ai_summary"])

    return JsonResponse({"success": True, "summary": summary, "cached": False})