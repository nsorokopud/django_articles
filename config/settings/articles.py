from .env import env


DEFAULT_DRAFT_ARTICLE_TITLE = "Untitled article"

ALLOWED_ARTICLE_CONTENT_URL_SCHEMES = set(
    env.list("ALLOWED_ARTICLE_CONTENT_URL_SCHEMES", default=["https"])
)

ALLOWED_ARTICLE_INTERNAL_LINK_HOSTS = env.list("ALLOWED_ARTICLE_INTERNAL_LINK_HOSTS")

# Prefixes must start and end with "/", so prefixes like "/articles" are not allowed
ALLOWED_ARTICLE_INTERNAL_LINK_PREFIXES = ("/articles/", "/author/")
