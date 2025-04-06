function tinymceUploadHandler(blobInfo, progress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.withCredentials = false;
    xhr.open('POST', '/tinymce/upload');
    xhr.setRequestHeader('X-CSRFToken', Cookies.get('csrftoken'));
    xhr.upload.onprogress = (e) => {
      progress((e.loaded / e.total) * 100);
    };
    xhr.onload = () => {
      if (xhr.status === 403) {
        reject({ message: 'HTTP Error: ' + xhr.status, remove: true });
        return;
      }

      if (xhr.status < 200 || xhr.status >= 300) {
        reject('HTTP Error: ' + xhr.status);
        return;
      }

      const response = JSON.parse(xhr.responseText);

      if (!response || typeof response.data.location != 'string') {
        reject('Invalid JSON: ' + xhr.responseText);
        return;
      }

      if (response.status == 'success') {
        resolve(response.data.location);
      } else {
        reject(`Error while uploading images! ${response.message}`);
        console.log(response.message);
      }
    };

    xhr.onerror = () => {
      reject(
        'Image upload failed due to a XHR Transport error. Code: ' + xhr.status,
      );
    };

    const formData = new FormData();
    formData.append('file', blobInfo.blob(), blobInfo.filename());

    try {
      let articleId = localStorage.getItem('createdArticleId');
      formData.append('articleId', articleId);
    } catch (e) {
      console.log(e);
    }

    xhr.send(formData);
  });
}
