function getCookie(cname) {
    let name = cname + "=";
    let ca = document.cookie.split(';');
    for(let i = 0; i < ca.length; i++)
    {
        let c = ca[i];
        while (c.charAt(0) == ' ')
        {
            c = c.substring(1);
        }
        if (c.indexOf(name) == 0)
        {
            return c.substring(name.length, c.length);
        }
    }
    return "";
}

function like_article()
{
    const likeLink = document.getElementById("articleLikeLink");
    const likeIcon = document.getElementById("articleLikeIcon");
    const likesCounter = document.getElementById("articleLikesCounter");
    
    
        likeLink.onclick = (e) => {
            e.preventDefault();
            if (likeLink.hasAttribute("is_logged_in"))
            {
                let xhr = new XMLHttpRequest();
                let url = likeLink.href;
                
                let csrftoken = getCookie("csrftoken");

                xhr.open("POST", url, true);
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
                xhr.dataType = "json";
                xhr.responseType = "json"
                xhr.send();
                
                xhr.onload = function() {
                    response = xhr.response;
                    likeIcon.classList.toggle("active");
                    likesCounter.textContent = response["likes_count"];
                };
            }
            else
            {
                alert("Please, log in if you want to like an article!");
            }
        }
    
}

function like_comment(e, comment_id)
{
    e.preventDefault();
    comment = document.getElementById("comment" + comment_id);

    if (comment.hasAttribute("is_logged_in"))
    {
        let xhr = new XMLHttpRequest();
        let url = comment.href;
        
        let csrftoken = getCookie("csrftoken");

        xhr.open("POST", url, true);
        xhr.setRequestHeader("X-CSRFToken", csrftoken);
        xhr.dataType = "json";
        xhr.responseType = "json"
        xhr.send();
        
        xhr.onload = function() {
            response = xhr.response;
            comment.getElementsByTagName("i")[0].classList.toggle("active");
            comment.getElementsByClassName("comment-like-count")[0]
                .textContent = response["comment_likes_count"];
        };
    }
    else
    {
        alert("Please, log in if you want to like a comment!");
    }
}


like_article();