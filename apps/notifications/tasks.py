from articles.services import get_article_by_slug
from config.celery import app


@app.task
def send_new_article_notification(article_slug: str) -> None:
    from .services import send_new_article_notification
    
    article = get_article_by_slug(article_slug)
    send_new_article_notification(article)
