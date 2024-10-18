document.addEventListener("DOMContentLoaded", function() {
    console.log("DOM fully loaded and parsed");

    // Handle login redirection
    const loginButton = document.getElementById('loginButton');
    if (loginButton) {
        loginButton.addEventListener('click', function() {
            const clientId = 'RuJCiXFIyWKR-EzESJJjMA';
            const redirectUri = 'http://localhost:3000/callback';
            const responseType = 'code';
            const scope = 'read';
            const authUrl = `https://www.reddit.com/api/v1/authorize?client_id=${clientId}&response_type=${responseType}&state=random_state_string&redirect_uri=${encodeURIComponent(redirectUri)}&scope=${scope}`;
            window.location.href = authUrl;
        });
    }

    // Fetch posts from server
    fetch('/posts')
    .then(response => response.json())
    .then(data => {
        const postsContainer = document.querySelector('ul');
        data.forEach(post => {
            const markup = `<li><a href="${post.url}" target="_blank" data-post-id="${post.id}" class="reddit-post-link">${post.title}</a></li>`;
            postsContainer.insertAdjacentHTML('beforeend', markup);
        });
        console.log("Posts added to HTML");
    })
    .catch(error => console.error("Error fetching posts:", error));
});

