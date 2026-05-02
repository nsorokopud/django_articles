document.getElementById('articleForm').addEventListener('submit', (e) => {
  const form = e.target;
  const isFormValid = form.checkValidity();

  if (!isFormValid) {
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
  removeFormValidationErrors();

  const form = document.getElementById('articleForm');
  const articleSlug = document.getElementById('articleSlug').value;
  const editor = tinymce.activeEditor;

  if (!editor) {
    alert('Editor is not ready yet. Please try again.');
    return;
  }

  const content = editor.getBody();
  const containsUploadedImages = checkIfContentContainsUploadedImages(content);

  if (containsUploadedImages) {
    editor
      .uploadImages()
      .then(() => {
        updateArticle(articleSlug, form, editor);
      })
      .catch((error) => {
        console.error('TinyMCE image upload failed:', error);
      });
  } else {
    updateArticle(articleSlug, form, editor);
  }
}

function updateArticle(articleSlug, form, editor) {
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
      alert('Unexpected server response while updating article.');
      console.error('Invalid JSON response:', xhr.responseText);
      return;
    }

    if (xhr.status === 200 && response.status === 'success') {
      window.location.replace(response.data.articleUrl);
    } else if (xhr.status === 400 && response.status === 'fail') {
      displayFormValidationErrors(response);
    } else {
      alert('Error while updating article!');
      console.log(response);
    }
  };

  xhr.onerror = () => {
    alert('Network error while updating article. Please try again.');
  };

  xhr.ontimeout = () => {
    alert('Article update timed out. Please try again.');
  };

  const formData = new FormData(form);
  formData.set('content', editor.getContent());
  xhr.send(formData);
}

function checkIfContentContainsUploadedImages(content) {
  const images = content.getElementsByTagName('img');
  for (const el of images) {
    if (el.src.startsWith('blob:')) return true;
  }
  return false;
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
