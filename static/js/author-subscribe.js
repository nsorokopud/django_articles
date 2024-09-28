const authorSubscribeButton = document.getElementById('authorSubscribeButton');
authorSubscribeButton.onclick = (e) => {
    if (!authorSubscribeButton.hasAttribute('isLoggedIn')) {
        e.preventDefault();
        alert('Please log in to be able to subscribe/unsubscribe!')
    }
}
