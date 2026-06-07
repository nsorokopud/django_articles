TINYMCE_JS_URL = "https://cdn.jsdelivr.net/npm/tinymce@7.3.0/tinymce.min.js"

TINYMCE_EXTRA_MEDIA = {
    "js": ["js/tinymce-upload-handler.js", "js/tinymce-setup.js"],
}

TINYMCE_DEFAULT_CONFIG = {
    "theme": "silver",
    "height": 750,
    "width": "100%",
    "menubar": False,
    "promotion": False,
    "license_key": "gpl",
    "plugins": (
        "autolink link image advlist lists table codesample charmap fullscreen"
    ),
    "toolbar": [
        "undo redo | fullscreen | hr uploadimage table codesample blockquote | charmap",
        "blocks | bullist numlist indent outdent | alignleft aligncenter alignright"
        " alignjustify",
        "fontfamily fontsize | bold italic underline strikethrough | removeformat",
    ],
    "file_picker_types": "image",
    "image_url_input": False,
    "images_upload_url": "/tinymce/upload/",
    "images_upload_handler": "tinymceUploadHandler",
    "automatic_uploads": False,
    "convert_urls": False,
    "relative_urls": False,
    "remove_script_host": True,
    "invalid_elements": (
        "script,iframe,object,embed,form,input,button,select,textarea,style"
    ),
    "setup": "tinymceCustomSetup",
    "content_css": ["/static/css/tinymce-content.css"],
    "object_resizing": "table",
}
