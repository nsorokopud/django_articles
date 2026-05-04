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

  function removeRemoteImages() {
    let removed = false;

    editor.dom.select('img').forEach(function (img) {
      const src = img.getAttribute('src') || '';

      if (
        src.startsWith('http://') ||
        src.startsWith('https://') ||
        src.startsWith('//') ||
        src.startsWith('data:')
      ) {
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
