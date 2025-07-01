function tinymceUploadHandler(blobInfo, progress) {
  const uploadPromise = new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();

    xhr.open('POST', '/tinymce/upload');
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    xhr.setRequestHeader('X-CSRFToken', Cookies.get('csrftoken'));
    xhr.withCredentials = false;

    formData.append('file', blobInfo.blob(), blobInfo.filename());

    try {
      const articleId = localStorage.getItem('createdArticleId');
      if (articleId) {
        formData.append('articleId', articleId);
      }
    } catch (err) {
      console.warn('Failed to get article ID from localStorage', err);
    }

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        progress((e.loaded / e.total) * 100);
      }
    };

    xhr.timeout = 30000; // 30 seconds
    xhr.ontimeout = () => {
      reject({ message: 'Upload timed out. Try again.', remove: true });
    };

    xhr.onerror = () => {
      console.error('Network or transport error during upload:', xhr.status);
      reject({
        message: 'Network error while uploading the file. Please try again.',
        remove: true,
      });
    };

    xhr.onload = () => {
      let response = null;

      try {
        response = JSON.parse(xhr.responseText);
      } catch (err) {
        console.error(
          'Invalid JSON response from file upload endpoint',
          xhr.responseText,
        );
        if (xhr.status === 413) {
          return reject({
            message: 'The file is too big.',
            remove: true,
          });
        } else {
          return reject({
            message: 'Unexpected server response format.',
            remove: true,
          });
        }
      }

      const errorMessages = {
        400: response?.message || 'Invalid media file.',
        403: 'You have no permission to edit this article.',
        404: 'That article does not exist.',
        500: 'Server error while saving the file. Please try again.',
      };

      if (xhr.status === 200 && response.status === 'success') {
        const location = response?.data?.location;
        if (typeof location === 'string') {
          return resolve(location);
        }
        return reject({
          message: 'Upload succeeded but response format was invalid.',
          remove: true,
        });
      } else if (errorMessages[xhr.status]) {
        return reject({ message: errorMessages[xhr.status], remove: true });
      } else {
        return reject({
          message: 'Unexpected server response. Please try again.',
          remove: true,
        });
      }
    };

    xhr.send(formData);
  });
  return uploadPromise.catch((error) => {
    alert(
      `${error.message || 'Unknown upload error'} ` +
        'You will now be redirected back to the article page.',
    );
    return Promise.reject(error);
  });
}
