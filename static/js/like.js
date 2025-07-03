likeArticle();

function likeArticle() {
  const likeLink = document.getElementById('articleLikeLink');
  const likeIcon = document.getElementById('articleLikeIcon');
  const likesCounter = document.getElementById('articleLikesCounter');

  likeLink.onclick = (e) => {
    e.preventDefault();
    if (likeLink.hasAttribute('is_logged_in')) {
      let xhr = new XMLHttpRequest();
      let url = likeLink.href;

      let csrftoken = Cookies.get('csrftoken');

      xhr.open('POST', url, true);
      xhr.setRequestHeader('X-CSRFToken', csrftoken);
      xhr.dataType = 'json';
      xhr.responseType = 'json';
      xhr.send();

      xhr.onload = function () {
        let response = xhr.response;
        likeIcon.classList.toggle('active');
        likesCounter.textContent = response['likes_count'];
      };
    } else {
      alert('Please, log in if you want to like an article!');
    }
  };
}

function likeComment(e, comment_id) {
  e.preventDefault();
  let commentLink = document.getElementById('commentLink' + comment_id);

  if (commentLink.hasAttribute('is_logged_in')) {
    let xhr = new XMLHttpRequest();
    let url = commentLink.href;

    let csrftoken = Cookies.get('csrftoken');

    xhr.open('POST', url, true);
    xhr.setRequestHeader('X-CSRFToken', csrftoken);
    xhr.dataType = 'json';
    xhr.responseType = 'json';
    xhr.send();

    xhr.onload = function () {
      let response = xhr.response;
      commentLink.getElementsByTagName('i')[0].classList.toggle('active');
      commentLink.getElementsByClassName('comment-like-count')[0].textContent =
        response['comment_likes_count'];
    };
  } else alert('Please, log in if you want to like a comment!');
}
