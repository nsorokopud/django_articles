$('#articleFormCreateButton').click((e) => {
  let form = document.getElementById('articleForm');
  let isFormValid = form.checkValidity();
  if (!isFormValid) {
    document.documentElement.style.scrollBehavior = 'auto';
    form.reportValidity();
    document.documentElement.style.scrollBehavior = '';
  } else {
    e.preventDefault();
    onArticleFormCreateButtonClick();
  }
});

$('#articleFormUpdateButton').click((e) => {
  let form = document.getElementById('articleForm');
  let isFormValid = form.checkValidity();
  if (!isFormValid) {
    document.documentElement.style.scrollBehavior = 'auto';
    form.reportValidity();
    document.documentElement.style.scrollBehavior = '';
  } else {
    e.preventDefault();
    onArticleFormUpdateButtonClick();
  }
  onArticleFormUpdateButtonClick();
});

function onArticleFormCreateButtonClick() {
  removeFormValidationErrors();

  let form = document.getElementById('articleForm');

  let xhr = new XMLHttpRequest();
  xhr.open('POST', '/articles/create');
  xhr.setRequestHeader('X-CSRFToken', Cookies.get('csrftoken'));
  xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');

  xhr.onload = () => {
    if (xhr.status != 200) {
      alert(`Error (HTTP: ${xhr.status}) while creating article!`);
      return;
    }

    let response = JSON.parse(xhr.responseText);

    if (response.status == 'success') {
      localStorage.setItem('createdArticleId', response.data.articleId);

      let content = tinymce.activeEditor.getBody();
      let containsUploadedImages =
        checkIfContentContainsUploadedImages(content);

      if (containsUploadedImages) {
        tinymce.activeEditor.uploadImages().then(() => {
          updateArticle(response.data.articleSlug, form, tinymce.activeEditor);
        });
      } else {
        updateArticle(response.data.articleSlug, form, tinymce.activeEditor);
      }
    } else if (response.status == 'fail') {
      displayFormValidationErrors(response);
    } else if (response.status == 'error') {
      alert(`Error while creating article! ${response.message}`);
      console.log(response.message);
    }
  };

  let formData = new FormData(form);
  formData.set('content', tinymce.activeEditor.getContent());
  xhr.send(formData);
}

function onArticleFormUpdateButtonClick() {
  removeFormValidationErrors();

  let form = document.getElementById('articleForm');
  let articleId = document.getElementById('articleId').value;
  let articleSlug = document.getElementById('articleSlug').value;
  let content = tinymce.activeEditor.getBody();

  let containsUploadedImages = checkIfContentContainsUploadedImages(content);

  if (containsUploadedImages) {
    localStorage.setItem('createdArticleId', articleId);
    tinymce.activeEditor.uploadImages().then(() => {
      updateArticle(articleSlug, form, tinymce.activeEditor);
    });
  } else {
    updateArticle(articleSlug, form, tinymce.activeEditor);
  }
}

function updateArticle(articleSlug, form, editor) {
  xhr = new XMLHttpRequest();
  xhr.open('POST', `/articles/${articleSlug}/edit`);
  xhr.setRequestHeader('X-CSRFToken', Cookies.get('csrftoken'));
  xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');

  xhr.onload = () => {
    response = JSON.parse(xhr.responseText);
    if (response.status == 'success') {
      localStorage.removeItem('createdArticleId');
      window.location.replace(response.data.articleUrl);
    } else if (response.status == 'fail') {
      displayFormValidationErrors(response);
    } else if (response.status == 'error') {
      alert(`Error while updating article! ${response.message}`);
      console.log(response.message);
    }
  };

  let formData = new FormData(form);
  formData.set('content', editor.getContent());
  xhr.send(formData);
}

function checkIfContentContainsUploadedImages(content) {
  let images = content.getElementsByTagName('img');
  for (el of images) if (el.src.startsWith('blob:')) return true;
  return false;
}

function removeFormValidationErrors() {
  $('.form-group .form-control').removeClass('is-invalid');
  $('.invalid-feedback').remove();
}

function displayFormValidationErrors(response) {
  for (field in response.data) {
    let fieldId = 'id_' + field;
    let input = document.getElementById(fieldId);
    if (!input.classList.contains('is-invalid')) {
      input.classList.add('is-invalid');
      let errorMessage = document.createElement('div');
      errorMessage.classList.add('invalid-feedback');
      errorMessage.innerText = response.data[field][0];
      input.parentNode.appendChild(errorMessage);
    }
  }
}
