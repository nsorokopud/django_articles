import os


# Indicates how many articles will be displayed by paginator on the home page
ARTICLES_PER_PAGE_COUNT = int(os.getenv("ARTICLES_PER_PAGE_COUNT", "5"))

# Indicates how many chars of a long comment will be displayed by __str__ method
DISPLAYED_COMMENT_LENGTH = int(os.getenv("DISPLAYED_COMMENT_LENGTH", "25"))

# Sets a time period (in seconds) during which the article view counter
# will be incremented only once per unique viewer.
ARTICLE_UNIQUE_VIEW_TIMEOUT = int(
    os.getenv("ARTICLE_UNIQUE_VIEW_TIMEOUT", "3600")  # 1 hour
)

# Article details page cache timeout (for anonymous users only) in seconds.
ARTICLE_DETAILS_PAGE_CACHE_TIMEOUT = int(
    os.getenv("ARTICLE_DETAILS_PAGE_CACHE_TIMEOUT", "300")  # 5 minutes
)

# Max number of iterations when syncing article views from cache to database.
ARTICLE_VIEW_SYNC_MAX_ITERATIONS = int(
    os.getenv("ARTICLE_VIEW_SYNC_MAX_ITERATIONS", "20")
)

# Max number of articles to process in each batch when syncing article views.
ARTICLE_VIEW_SYNC_MAX_BATCH_SIZE = int(
    os.getenv("ARTICLE_VIEW_SYNC_MAX_BATCH_SIZE", "500")
)
