document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.like-link').forEach((link) => {
    link.addEventListener('click', function (e) {
      e.preventDefault();
      handleLike(link);
    });
  });
});

function handleLike(linkEl) {
  const isLoggedIn = linkEl.dataset.loggedIn === 'yes';
  const url = linkEl.getAttribute('href');

  if (!isLoggedIn) {
    alert(`Please, log in to like this ${linkEl.dataset.type}!`);
    return;
  }

  const iconEl = linkEl.querySelector('.like-icon');
  const counterEl =
    linkEl.querySelector('.like-counter') ||
    linkEl.parentElement.querySelector('.like-counter');
  const csrftoken = Cookies.get('csrftoken');

  const xhr = new XMLHttpRequest();
  xhr.open('POST', url, true);
  xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
  xhr.setRequestHeader('X-CSRFToken', csrftoken);
  xhr.responseType = 'json';
  xhr.send();

  xhr.onload = function () {
    if (xhr.status === 200 && xhr.response) {
      const { status, data } = xhr.response;

      if (
        status === 'success' &&
        data &&
        typeof data.likes_count === 'number'
      ) {
        iconEl?.classList.toggle('active');
        counterEl.textContent = data.likes_count;
      } else {
        console.error('Unexpected response format:', xhr.response);
        alert('Something went wrong. Please try again.');
      }
    } else {
      console.error('Like request failed. Status:', xhr.status, xhr.response);
      alert('Failed to like. Please try again later.');
    }
  };

  xhr.onerror = function () {
    console.error('Network error occurred during like request.');
    alert('Network error. Please check your connection.');
  };
}
