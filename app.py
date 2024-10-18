from flask import Flask, json, redirect, render_template, request, jsonify, session, url_for
from datetime import datetime
import requests
import os
from kafka import KafkaProducer
from pymongo import MongoClient

app = Flask(__name__, template_folder='serendyzetest/templates', static_folder='serendyzetest/static/css')
app.secret_key = os.urandom(16)

# Kafka Producer Configuration
producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],  # Local Kafka server
    value_serializer=lambda v: json.dumps(v).encode('utf-8')  # JSON serialization
)

CLIENT_ID = 'RuJCiXFIyWKR-EzESJJjMA'
CLIENT_SECRET = 'qjCh1iI0UYLNsl4LyAW4F31Noed2_w'
REDIRECT_URI = 'http://localhost:3000/callback'
scope = 'identity read'

# Cache to store user details
user_cache = {}

def calculate_popularity_rating(upvote_ratio):
    if upvote_ratio >= 0.9:
        return 5
    elif upvote_ratio >= 0.7:
        return 4
    elif upvote_ratio >= 0.5:
        return 3
    elif upvote_ratio >= 0.3:
        return 2
    else:
        return 1

def fetch_replies(comment_data, headers):
    replies = []
    if 'replies' in comment_data and comment_data['replies'] and comment_data['replies'] != '':
        replies_data = comment_data['replies'].get('data', {}).get('children', [])
        for reply in replies_data:
            if 'data' in reply:
                reply_info = {
                    'author': reply['data'].get('author', 'Unknown'),
                    'text': reply['data'].get('body', ''),
                    'replies': fetch_replies(reply['data'], headers)  # Recursively fetch nested replies
                }
                replies.append(reply_info)
    return replies

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login')
def login():
    auth_url = (
        f"https://www.reddit.com/api/v1/authorize?"
        f"client_id={CLIENT_ID}&response_type=code&state=random_state_string&"
        f"redirect_uri={REDIRECT_URI}&duration=temporary&scope=identity read"
    )
    return redirect(auth_url)

@app.route('/callback')
def callback():
    error = request.args.get('error')
    if error:
        return f'Error from Reddit: {error}', 400
    code = request.args.get('code')
    if not code:
        return 'Error: Missing authorization code', 400

    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    headers = {'User-Agent': 'YourAppName'}
    auth = (CLIENT_ID, CLIENT_SECRET)

    token_response = requests.post(
        'https://www.reddit.com/api/v1/access_token',
        auth=auth,
        data=data,
        headers=headers
    )

    if token_response.status_code != 200:
        return f'Failed to fetch token. Response: {token_response.text}', 500

    access_token = token_response.json().get('access_token')
    if not access_token:
        return 'Failed to fetch access token', 500

    session['access_token'] = access_token

    profile_response = requests.get(
        'https://oauth.reddit.com/api/v1/me',
        headers={'Authorization': f'Bearer {access_token}', 'User-Agent': 'YourAppName'}
    )

    if profile_response.status_code != 200:
        return f'Failed to fetch user profile. Response: {profile_response.text}', 500

    user_profile = profile_response.json()
    session['username'] = user_profile.get('name')
    session['user_id'] = user_profile.get('id')
    session['link_karma'] = user_profile.get('link_karma', 0)
    session['comment_karma'] = user_profile.get('comment_karma', 0)
    session['created_utc'] = user_profile.get('created_utc')

    return redirect('/posts')


@app.route('/posts')
def posts():
    access_token = session.get('access_token')
    if not access_token:
        return redirect(url_for('login'))

    headers = {
        'Authorization': f'Bearer {access_token}',
        'User-Agent': 'YourAppName'
    }
    response = requests.get('https://oauth.reddit.com/r/popular', headers=headers)

    if response.status_code != 200:
        return 'Failed to fetch posts', 500

    try:
        random_posts = response.json()
        if isinstance(random_posts, list):
            random_posts = random_posts[0]

        posts = random_posts.get('data', {}).get('children', [])
        posts_data = []
        for post in posts:
            data = post['data']
            subreddit = data.get('subreddit', 'Unknown')
            ups = data['ups']
            downs = data['downs']
            upvote_ratio = data.get('upvote_ratio', 0)

            post_info = {
                'id': data['id'],
                'subreddit': subreddit,
                'title': data['title'],
                'ups': ups,
                'downs': downs,
                'author': data['author'],
                'text': data.get('selftext', ''),
                'url': f"https://www.reddit.com{data.get('permalink', '')}",
                'comments': [],
                'rating': calculate_popularity_rating(upvote_ratio),
                'upvote_ratio': upvote_ratio
            }
            posts_data.append(post_info)

        return render_template('posts.html', posts=posts_data)
    except (ValueError, KeyError) as e:
        return f'Failed to parse JSON response: {str(e)}', 500


@app.route('/log_click', methods=['POST'])
def log_click():
    click_data = request.get_json()
    print(f"Received click data: {click_data}")

    interaction_type = click_data.get('interaction_type')
    postid = click_data.get('postid')
    posttitle = click_data.get('posttitle')
    subreddit = click_data.get('subreddit')
    timestamp = click_data.get('timestamp')

    username = session.get('username', 'Unknown User')
    user_id = session.get('user_id', 'Unknown ID')
    link_karma = session.get('link_karma', 0)
    comment_karma = session.get('comment_karma', 0)
    total_karma = link_karma + comment_karma
    created_utc = session.get('created_utc', 'Unknown')

    if not postid or not posttitle or not interaction_type: #subreddit
        return "Invalid data", 400

    interaction_data = {
        'interaction_type': interaction_type,
        'post_id': postid,
        'post_title': posttitle,
        'subreddit': subreddit,
        'timestamp': timestamp
    }

    log_entry = {
        'username': username,
        'user_id': user_id,
        'link_karma': link_karma,
        'comment_karma': comment_karma,
        'total_karma': total_karma,
        'created_utc': created_utc,
        'interactions': [interaction_data]
    }

    producer.send('user_clicks', value=log_entry)
    producer.flush()

    return 'Click logged and sent to Kafka', 200


if __name__ == '__main__':
    app.run(debug=True, port=3000, use_reloader=True)
