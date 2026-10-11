# NewsMind 📰

**AI-Powered News Summarization Web Application**

NewsMind is a Django-based web application that helps users explore news articles and understand stories more quickly through AI-generated summaries and key points.

## Features

- **News Feed:** Browse the latest available news articles.
- **Category Browsing:** Explore articles by news category.
- **Article Cards:** View headlines, publishers, and available article descriptions.
- **AI Summarization:** Request AI-generated summaries through the Gemini integration.
- **Source Links:** Visit the original publisher's article.
- **Feed Caching:** Reuse cached news data to reduce repeated API requests.
- **Responsive Interface:** Browse the news feed across supported screen sizes.

## Technology Stack

- **Backend:** Python, Django
- **Frontend:** HTML, CSS, JavaScript, Django Templates
- **Database:** SQLite
- **News Data:** External news API
- **AI Integration:** Google Gemini API
- **Configuration:** Environment variables using `python-dotenv`

## Project Structure

```text
newsmind/
├── manage.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── news/
│   ├── migrations/
│   ├── services/
│   │   ├── news_api.py
│   │   └── summarizer.py
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   └── tests.py
└── newsmind/
    ├── settings.py
    ├── urls.py
    ├── asgi.py
    └── wsgi.py
```

## Getting Started

### Prerequisites

- Python 3.12 or another version compatible with the project's dependencies
- pip
- API credentials for the configured news provider and Gemini, where required

### Installation

1. Clone the repository:

   ```bash
   git clone YOUR_REPOSITORY_URL
   cd NewsMind
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   ```

   Windows PowerShell:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

4. Create a local `.env` file based on `.env.example` and configure the required environment variables.

5. Apply database migrations:

   ```bash
   python manage.py migrate
   ```

6. Start the development server:

   ```bash
   python manage.py runserver
   ```

7. Open `http://127.0.0.1:8000/` in your browser.

## Environment Configuration

Configure the variables required by the current implementation in your local `.env` file.

```dotenv
SECRET_KEY=replace_with_your_django_secret_key
DEBUG=True
NEWS_API_KEY=replace_with_your_news_provider_key
GEMINI_API_KEY=replace_with_your_gemini_key
```

These values are placeholders. Never commit real API keys or production secrets to GitHub. Set `DEBUG=False` for production and configure the appropriate allowed hosts and security settings.

## Architecture

NewsMind uses Django views to handle browser requests, service modules to communicate with external APIs, and a `CachedArticle` model to store article metadata and summaries.

The homepage retrieves news through the news service and uses caching to reduce repeated fetching. When a user requests an AI summary, the application processes the request through the summarization service and returns the result to the browser.

See [`docs/architecture.md`](docs/architecture.md) for the architecture diagram and additional technical details.

## Testing

Run the Django system checks:

```bash
python manage.py check
```

Run the automated tests:

```bash
python manage.py test
```

## Known Issues and Limitations

- Feed cache entries may be process-local when using Django's local-memory cache and can disappear when the server restarts.
- The `home_feed()` endpoint and its referenced article-card template require verification because the endpoint is not currently registered in the URL configuration.
- The loading skeleton template requires integration with the homepage before it can provide a loading state.
- API availability, rate limits, missing article images, and inaccessible article content may affect the news feed and summaries.
- Production deployment requires verified secret management, appropriate host configuration, and `DEBUG=False`.

These limitations should be updated as the implementation changes.

## Future Improvements

- Add pagination or a load-more feature for larger feeds.
- Improve automated tests for news retrieval and AI summarization.
- Add more robust caching and error handling.
- Optimize article image loading and page performance.
- Configure production deployment and monitoring.

## Security

- Keep `.env`, local databases, and virtual environments out of version control.
- Commit `.env.example` with placeholder values only.
- Rotate any API credentials that have been exposed.
- Never publish secrets in source code, documentation, screenshots, or Git history.

## License

No license has been selected yet. Add a license before permitting others to reuse or distribute the project.
