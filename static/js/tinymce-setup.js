function getMediaAllowedRootUrls() {
  const script = document.getElementById('mediaAllowedRootUrls');

  if (!script) {
    return [];
  }

  try {
    return JSON.parse(script.textContent || '[]');
  } catch {
    return [];
  }
}

function tinymceCustomSetup(editor) {
  // Image upload button
  editor.ui.registry.addButton('uploadimage', {
    icon: 'image',
    tooltip: 'Upload image',
    onAction: function () {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'image/*';

      input.onchange = function () {
        const file = input.files && input.files[0];
        if (!file) return;

        const reader = new FileReader();

        reader.onload = function () {
          const id = 'blobid' + new Date().getTime();
          const blobCache = editor.editorUpload.blobCache;
          const base64 = reader.result.split(',')[1];
          const blobInfo = blobCache.create(id, file, base64);
          blobCache.add(blobInfo);

          editor.insertContent(
            '<p><img src="' + blobInfo.blobUri() + '" alt=""></p>',
          );

          editor.notificationManager.open({
            text: 'Image added. It will be uploaded when you save the draft.',
            type: 'info',
          });
        };

        reader.onerror = function () {
          editor.notificationManager.open({
            text: 'Could not read the selected image. Please try again.',
            type: 'error',
          });
        };

        reader.readAsDataURL(file);
      };

      input.click();
    },
  });

  const mediaAllowedRootUrls = getMediaAllowedRootUrls();

  function isAllowedEditorImageSrc(src) {
    if (!src) {
      return false;
    }

    // Allow temporary images
    if (src.startsWith('blob:')) {
      return true;
    }

    // Allow local/dev/proxied media URLs
    if (src.startsWith('/media/articles/uploads/')) {
      return true;
    }

    // Disallow pasted inline base64 images
    if (src.startsWith('data:')) {
      return false;
    }

    // Disallow protocol-relative URLs
    if (src.startsWith('//')) {
      return false;
    }

    // Allow absolute URLs only from configured media/CDN roots
    if (src.startsWith('http://') || src.startsWith('https://')) {
      return mediaAllowedRootUrls.some((root) => src.startsWith(root));
    }

    return false;
  }

  function removeRemoteImages() {
    let removed = false;

    editor.dom.select('img').forEach(function (img) {
      const src = img.getAttribute('src') || '';

      if (!isAllowedEditorImageSrc(src)) {
        img.remove();
        removed = true;
      }
    });

    if (removed) {
      editor.notificationManager.open({
        text: 'Only uploaded images are allowed.',
        type: 'warning',
      });
    }
  }

  editor.on(
    'PastePostProcess SetContent Change Input Undo Redo Drop',
    function () {
      setTimeout(removeRemoteImages, 0);
    },
  );
}
