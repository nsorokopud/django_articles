from articles.services import get_article_by_slug,  get_comment_by_id
from users.services import get_user_by_id
from config.celery import app


@app.task
def send_new_article_notification(article_slug: str) -> None:
    from .services import send_new_article_notification
    
    article = get_article_by_slug(article_slug)
    send_new_article_notification(article)


@app.task
def send_new_comment_notification(comment_id: int, recipient_id: int) -> None:
    from .services import send_new_comment_notification
    
    comment = get_comment_by_id(comment_id)
    recipient = get_user_by_id(recipient_id)
    send_new_comment_notification(comment, recipient)