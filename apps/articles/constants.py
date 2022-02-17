import os


# Indicates how many articles will be displayed by paginator on the home page
ARTICLES_PER_PAGE_COUNT = int(os.getenv("ARTICLES_PER_PAGE_COUNT", 5))

# Indicates how many chars of a long comment will be displayed on the admin page
DISPLAYED_COMMENT_LENGTH = int(os.getenv("DISPLAYED_COMMENT_LENGTH", 25))
