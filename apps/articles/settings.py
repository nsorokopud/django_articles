import os


# Indicates how many articles will be displayed by paginator on the home page
ARTICLES_PER_PAGE_COUNT = int(os.getenv("ARTICLES_PER_PAGE_COUNT", "5"))

# Indicates how many chars of a long comment will be displayed by __str__ method
DISPLAYED_COMMENT_LENGTH = int(os.getenv("DISPLAYED_COMMENT_LENGTH", "25"))


# Max number of iterations when syncing article views from cache to database.
ARTICLE_VIEW_SYNC_MAX_ITERATIONS = int(
    os.getenv("ARTICLE_VIEW_SYNC_MAX_ITERATIONS", "20")
)

# Max number of articles to process in each batch when syncing article views.
ARTICLE_VIEW_SYNC_MAX_BATCH_SIZE = int(
    os.getenv("ARTICLE_VIEW_SYNC_MAX_BATCH_SIZE", "500")
)
