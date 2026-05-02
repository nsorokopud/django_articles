document.addEventListener('click', (e) => {
  const link = e.target.closest('.like-link');

  if (!link) {
    return;
  }

  e.preventDefault();
  handleLike(link);
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

  const liked = !iconEl.classList.contains('active');

  fetch(url, {
    method: 'POST',
    headers: {
      'X-Requested-With': 'XMLHttpRequest',
      'X-CSRFToken': Cookies.get('csrftoken'),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ liked }),
  })
    .then(async (response) => {
      const payload = await response.json().catch(() => ({}));

      if (!response.ok || payload.status !== 'success') {
        throw new Error(
          payload.message || 'Failed to like. Please try again later.',
        );
      }

      return payload;
    })
    .then((payload) => {
      iconEl.classList.toggle('active', payload.data.liked);
      counterEl.textContent = payload.data.likes;
    })
    .catch((error) => {
      console.error(error);
      alert(error.message || 'Something went wrong.');
    });
}
