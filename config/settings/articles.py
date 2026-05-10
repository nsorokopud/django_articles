import os


DEFAULT_DRAFT_ARTICLE_TITLE = "Untitled article"

ALLOWED_ARTICLE_CONTENT_URL_SCHEMES = set(
    os.getenv("ALLOWED_ARTICLE_CONTENT_URL_SCHEMES", "https").split(" ")
)

ALLOWED_ARTICLE_INTERNAL_LINK_HOSTS = os.environ[
    "ALLOWED_ARTICLE_INTERNAL_LINK_HOSTS"
].split(" ")

# Prefixes must start and end with "/", so prefixes like "/articles" are not allowed
ALLOWED_ARTICLE_INTERNAL_LINK_PREFIXES = ("/articles/", "/author/")
