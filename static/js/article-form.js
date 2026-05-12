const articleForm = document.getElementById('articleForm');

if (articleForm) {
  articleForm.addEventListener('submit', (e) => {
    const form = e.target;

    if (!form.checkValidity()) {
      document.documentElement.style.scrollBehavior = 'auto';
      form.reportValidity();
      document.documentElement.style.scrollBehavior = '';
      e.preventDefault();
      return;
    }

    e.preventDefault();
    onArticleFormSaveButtonClick(e.submitter);
  });
}

function onArticleFormSaveButtonClick(submitter) {
  const button =
    submitter || document.getElementById('articleFormUpdateButton');

  if (button && button.disabled) {
    return;
  }

  removeFormValidationErrors();

  const articleId = document.getElementById('articleId')?.value;
  const editor = tinymce.activeEditor;

  setSubmitButtonLoading(button, submitter);

  if (!articleId) {
    restoreSubmitButton(button);
    alert('Article ID is missing. Please reload the page and try again.');
    return;
  }

  if (!editor) {
    restoreSubmitButton(button);
    alert('Editor is not ready yet. Please try again.');
    return;
  }

  editor
    .uploadImages()
    .then(() => {
      updateArticle(articleId, articleForm, editor, button, submitter);
    })
    .catch((error) => {
      console.error('TinyMCE image upload failed:', error);
      restoreSubmitButton(button);

      showEditorNotification(
        editor,
        error?.message || 'Image upload failed. Please try again.',
        'error',
      );
    });
}

function updateArticle(articleId, form, editor, button, submitter) {
  const xhr = new XMLHttpRequest();

  xhr.open('POST', form.action);
  xhr.setRequestHeader('X-CSRFToken', Cookies.get('csrftoken'));
  xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
  xhr.timeout = 30000;

  xhr.onload = () => {
    let response = null;

    try {
      response = JSON.parse(xhr.responseText);
    } catch (err) {
      restoreSubmitButton(button);
      alert('Unexpected server response while updating article.');
      console.error('Invalid JSON response:', xhr.responseText);
      return;
    }

    if (xhr.status === 200 && response.status === 'success') {
      window.location.replace(response.data.articleUrl);
      return;
    }

    restoreSubmitButton(button);

    if (xhr.status === 400 && response.status === 'fail') {
      displayFormValidationErrors(response);
      return;
    }

    alert(response?.message || 'Error while updating article!');
    console.log(response);
  };

  xhr.onerror = () => {
    restoreSubmitButton(button);
    alert('Network error while updating article. Please try again.');
  };

  xhr.ontimeout = () => {
    restoreSubmitButton(button);
    alert('Article update timed out. Please try again.');
  };

  const formData = new FormData(form);

  if (submitter?.name && submitter?.value) {
    formData.set(submitter.name, submitter.value);
  }

  formData.set('content', editor.getContent());
  xhr.send(formData);
}

function setSubmitButtonLoading(button, submitter) {
  setArticleFormBusy(true);

  if (!button) {
    return;
  }

  if (!button.dataset.originalText) {
    button.dataset.originalText = button.textContent;
  }

  button.textContent =
    submitter?.value === 'submit_for_review' ? 'Submitting...' : 'Saving...';
}

function setArticleFormBusy(isBusy) {
  document
    .querySelectorAll('#articleFormUpdateButton, #articleSubmitForReviewButton')
    .forEach((button) => {
      button.disabled = isBusy;
    });
}

function restoreSubmitButton(button) {
  setArticleFormBusy(false);

  if (!button) return;

  if (button.dataset.originalText) {
    button.textContent = button.dataset.originalText;
  }
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
    if (field === '__all__') {
      alert(response.data[field][0]);
      continue;
    }

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
