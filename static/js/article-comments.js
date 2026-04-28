document.addEventListener('DOMContentLoaded', () => {
  const button = document.getElementById('loadMoreCommentsButton');
  const container = document.querySelector('#commentsContainer .col-12');

  if (!button || !container) {
    return;
  }

  button.addEventListener('click', async () => {
    const nextPage = button.dataset.nextPage;
    const commentsUrl = button.dataset.commentsUrl;

    if (!nextPage || !commentsUrl) {
      return;
    }

    const originalText = button.textContent;

    button.disabled = true;
    button.textContent = 'Loading...';

    try {
      const url = new URL(commentsUrl, window.location.origin);
      url.searchParams.set('page', nextPage);

      const response = await fetch(url, {
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
        },
      });

      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }

      const payload = await response.json();

      if (
        payload.status !== 'success' ||
        typeof payload.html !== 'string' ||
        typeof payload.hasNext !== 'boolean'
      ) {
        throw new Error('Unexpected response format');
      }

      container.insertAdjacentHTML('beforeend', payload.html);

      if (payload.hasNext && payload.nextPage) {
        button.dataset.nextPage = payload.nextPage;
        button.disabled = false;
        button.textContent = originalText;
      } else {
        button.remove();
      }
    } catch (error) {
      console.error(error);
      button.disabled = false;
      button.textContent = originalText;
      alert('Could not load more comments. Please try again.');
    }
  });
});
