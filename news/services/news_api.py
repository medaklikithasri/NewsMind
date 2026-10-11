import os

import requests
from dotenv import load_dotenv


load_dotenv()


def fetch_news(query, page=1, page_size=20):

    api_key = os.getenv("NEWS_API_KEY")

    if not api_key or not query:
        return []

    url = "https://newsapi.org/v2/everything"

    try:
        response = requests.get(
            url,
            params={
                "q": query,
                "apiKey": api_key,
                "page": page,
                "pageSize": page_size,
                "sortBy": "publishedAt",
                "language": "en",
            },
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("status") == "ok":
            return data.get("articles", [])

        return []

    except (requests.RequestException, ValueError, KeyError):
        return []
