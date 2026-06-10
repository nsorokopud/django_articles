class ArticleCommentError(Exception):
    """Base class for expected comment-posting failures."""


class ArticleNotFoundCommentError(ArticleCommentError):
    """Raised when a comment target article does not exist."""


class ArticleNotPublishedCommentError(ArticleCommentError):
    """Raised when comments are not allowed for the target article."""
