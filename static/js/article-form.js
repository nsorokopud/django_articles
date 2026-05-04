document.getElementById('articleForm').addEventListener('submit', (e) => {
  const form = e.target;

  if (!form.checkValidity()) {
    document.documentElement.style.scrollBehavior = 'auto';
    form.reportValidity();
    document.documentElement.style.scrollBehavior = '';
    e.preventDefault();
    return;
  }

  e.preventDefault();
  onArticleFormSaveButtonClick();
});

function onArticleFormSaveButtonClick() {
  const saveButton = document.getElementById('articleFormUpdateButton');

  if (saveButton && saveButton.disabled) {
    return;
  }

  removeFormValidationErrors();

  const form = document.getElementById('articleForm');
  const articleSlug = document.getElementById('articleSlug').value;
  const editor = tinymce.activeEditor;

  setSaveButtonLoading(saveButton);

  if (!editor) {
    restoreSaveButton(saveButton);
    alert('Editor is not ready yet. Please try again.');
    return;
  }

  editor
    .uploadImages()
    .then(() => {
      updateArticle(articleSlug, form, editor, saveButton);
    })
    .catch((error) => {
      console.error('TinyMCE image upload failed:', error);
      restoreSaveButton(saveButton);

      showEditorNotification(
        editor,
        error?.message || 'Image upload failed. Please try again.',
        'error',
      );
    });
}

function updateArticle(articleSlug, form, editor, saveButton) {
  const xhr = new XMLHttpRequest();
  xhr.open('POST', `/articles/${articleSlug}/edit/`);
  xhr.setRequestHeader('X-CSRFToken', Cookies.get('csrftoken'));
  xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
  xhr.timeout = 30000;

  xhr.onload = () => {
    let response = null;

    try {
      response = JSON.parse(xhr.responseText);
    } catch (err) {
      restoreSaveButton(saveButton);
      alert('Unexpected server response while updating article.');
      console.error('Invalid JSON response:', xhr.responseText);
      return;
    }

    if (xhr.status === 200 && response.status === 'success') {
      window.location.replace(response.data.articleUrl);
      return;
    }

    restoreSaveButton(saveButton);

    if (xhr.status === 400 && response.status === 'fail') {
      displayFormValidationErrors(response);
      return;
    }

    alert(response?.message || 'Error while updating article!');
    console.log(response);
  };

  xhr.onerror = () => {
    restoreSaveButton(saveButton);
    alert('Network error while updating article. Please try again.');
  };

  xhr.ontimeout = () => {
    restoreSaveButton(saveButton);
    alert('Article update timed out. Please try again.');
  };

  const formData = new FormData(form);
  formData.set('content', editor.getContent());
  xhr.send(formData);
}

function setSaveButtonLoading(saveButton) {
  if (!saveButton) {
    return;
  }

  saveButton.disabled = true;

  if (!saveButton.dataset.originalText) {
    saveButton.dataset.originalText = saveButton.textContent;
  }

  saveButton.textContent = 'Saving...';
}

function restoreSaveButton(saveButton) {
  if (!saveButton) {
    return;
  }

  saveButton.disabled = false;
  saveButton.textContent = saveButton.dataset.originalText || 'Save draft';
}

function showEditorNotification(editor, message, type = 'info') {
  if (editor?.notificationManager) {
    editor.notificationManager.open({
      text: message,
      type,
    });
    return;
  }

  alert(message);
}

function removeFormValidationErrors() {
  $('.form-group .form-control').removeClass('is-invalid');
  $('.invalid-feedback').remove();
}

function displayFormValidationErrors(response) {
  for (const field in response.data) {
    const fieldId = 'id_' + field;
    const input = document.getElementById(fieldId);

    if (input && !input.classList.contains('is-invalid')) {
      input.classList.add('is-invalid');
      const errorMessage = document.createElement('div');
      errorMessage.classList.add('invalid-feedback');
      errorMessage.innerText = response.data[field][0];
      input.parentNode.appendChild(errorMessage);
    }
  }
}
