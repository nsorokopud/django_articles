class InvalidUpload(Exception):
    """Raised when an uploaded file fails validation."""


class MediaSaveError(Exception):
    """Raised when saving a media file to storage fails."""
