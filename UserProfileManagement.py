from flask import Flask, render_template, request, redirect, url_for, flash
from flask_restful import Api, Resource
import dash
from dash import dcc, html
import plotly.express as px
import pandas as pd
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
import tweepy
import aiohttp
import asyncio
import json
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
import facebook
import requests

# Initialize Flask
server = Flask(__name__)
server.secret_key = 'your_secret_key'
app = dash.Dash(__name__, server=server, url_base_pathname='/dashboard/')
api = Api(server)
bcrypt = Bcrypt(server)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = 'login'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    with open('users.json', 'r') as f:
        users = json.load(f)
    user_info = users.get(user_id)
    if user_info:
        return User(user_id=user_id, username=user_info['username'])
    return None

# Load settings
with open('settings.json', 'r') as f:
    settings = json.load(f)

# Google Analytics setup
SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']
KEY_FILE_LOCATION = settings['google_analytics']['key_file_location']
VIEW_ID = settings['google_analytics']['view_id']

def initialize_analyticsreporting():
    credentials = ServiceAccountCredentials.from_json_keyfile_name(KEY_FILE_LOCATION, SCOPES)
    analytics = build('analyticsreporting', 'v4', credentials=credentials)
    return analytics

def get_report(analytics):
    return analytics.reports().batchGet(
        body={
            'reportRequests': [
                {
                    'viewId': VIEW_ID,
                    'dateRanges': [{'startDate': '7daysAgo', 'endDate': 'today'}],
                    'metrics': [{'expression': 'ga:sessions'}, {'expression': 'ga:pageviews'}],
                    'dimensions': [{'name': 'ga:date'}]
                }]
        }
    ).execute()

def parse_response(response):
    report = response.get('reports', [])[0]
    rows = report.get('data', {}).get('rows', [])
    data = {
        'date': [],
        'sessions': [],
        'pageviews': []
    }
    for row in rows:
        data['date'].append(row['dimensions'][0])
        data['sessions'].append(int(row['metrics'][0]['values'][0]))
        data['pageviews'].append(int(row['metrics'][0]['values'][1]))
    return pd.DataFrame(data)

# Twitter API setup
TWITTER_CONSUMER_KEY = settings['twitter']['consumer_key']
TWITTER_CONSUMER_SECRET = settings['twitter']['consumer_secret']
TWITTER_ACCESS_TOKEN = settings['twitter']['access_token']
TWITTER_ACCESS_TOKEN_SECRET = settings['twitter']['access_token_secret']

auth = tweepy.OAuthHandler(TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET)
auth.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET)
twitter_api = tweepy.API(auth)

async def get_twitter_data():
    user_timeline = twitter_api.user_timeline(screen_name=settings['twitter']['handle'], count=10)
    data = {
        'date': [],
        'likes': [],
        'retweets': []
    }
    for tweet in user_timeline:
        data['date'].append(tweet.created_at)
        data['likes'].append(tweet.favorite_count)
        data['retweets'].append(tweet.retweet_count)
    return pd.DataFrame(data)

# Facebook API setup
FACEBOOK_ACCESS_TOKEN = settings['facebook']['access_token']

def get_facebook_data():
    graph = facebook.GraphAPI(access_token=FACEBOOK_ACCESS_TOKEN, version="3.1")
    profile = graph.get_object("me", fields="id,name,about,posts")
    posts = graph.get_connections(profile['id'], 'posts')
    data = {
        'date': [],
        'likes': [],
        'comments': []
    }
    for post in posts['data']:
        post_details = graph.get_object(post['id'], fields="created_time,likes.summary(true),comments.summary(true)")
        data['date'].append(post_details['created_time'])
        data['likes'].append(post_details['likes']['summary']['total_count'])
        data['comments'].append(post_details['comments']['summary']['total_count'])
    return pd.DataFrame(data)

# Instagram API setup
INSTAGRAM_ACCESS_TOKEN = settings['instagram']['access_token']

async def get_instagram_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://graph.instagram.com/me/media?fields=id,caption,media_type,media_url,permalink,thumbnail_url,timestamp,username&access_token={INSTAGRAM_ACCESS_TOKEN}") as response:
            posts = await response.json()
            data = {
                'date': [],
                'likes': [],
                'comments': []
            }
            for post in posts['data']:
                async with session.get(f"https://graph.instagram.com/{post['id']}?fields=like_count,comments_count&access_token={INSTAGRAM_ACCESS_TOKEN}") as post_response:
                    post_details = await post_response.json()
                    data['date'].append(post['timestamp'])
                    data['likes'].append(post_details['like_count'])
                    data['comments'].append(post_details['comments_count'])
            return pd.DataFrame(data)

# API endpoint for traffic data
class TrafficData(Resource):
    def get(self):
        analytics = initialize_analyticsreporting()
        response = get_report(analytics)
        data = parse_response(response)
        return data.to_dict(orient='records')

# API endpoint for social media data (Twitter)
class SocialMediaData(Resource):
    async def get(self):
        data = await get_twitter_data()
        return data.to_dict(orient='records')

# API endpoint for Facebook data
class FacebookData(Resource):
    async def get(self):
        data = get_facebook_data()
        return data.to_dict(orient='records')

# API endpoint for Instagram data
class InstagramData(Resource):
    async def get(self):
        data = await get_instagram_data()
        return data.to_dict(orient='records')

api.add_resource(TrafficData, '/api/traffic')
api.add_resource(SocialMediaData, '/api/socialmedia')
api.add_resource(FacebookData, '/api/facebook')
api.add_resource(InstagramData, '/api/instagram')

# Create sample data for conversion rates
conversion_data = pd.DataFrame({
    "Month": ["January", "February", "March"],
    "Conversions": [10, 20, 30]
})

# Create the dashboard layout
app.layout = html.Div(children=[
    dcc.Location(id='url', refresh=False),
    html.H1(children='Digital Marketing Dashboard'),
    html.Div([
        html.Nav([
            html.Ul([
                html.Li(html.A('Home', href='/')),
                html.Li(html.A('Traffic', href='/dashboard/traffic')),
                html.Li(html.A('Twitter', href='/dashboard/socialmedia')),
                html.Li(html.A('Facebook', href='/dashboard/facebook')),
                html.Li(html.A('Instagram', href='/dashboard/instagram')),
                html.Li(html.A('Conversions', href='/dashboard/conversions')),
                html.Li(html.A('Settings', href='/dashboard/settings')),
                html.Li(html.A('Profile', href='/dashboard/profile')),
                html.Li(html.A('Logout', href='/logout'))
            ])
        ])
    ]),
    html.Div(id='page-content')
])

# Callbacks for page navigation and data refresh
@app.callback(
    dash.dependencies.Output('page-content', 'children'),
    [dash.dependencies.Input('url', 'pathname'),
     dash.dependencies.Input('refresh-button', 'n_clicks')]
)
def display_page(pathname, n_clicks):
    if pathname == '/dashboard/traffic':
        # Fetch traffic data from the API
        traffic_response = requests.get("http://127.0.0.1:5000/api/traffic")
        traffic_data = pd.DataFrame(traffic_response.json())
        fig = px.line(traffic_data, x="date", y=["sessions", "pageviews"], title="Website Traffic")
        return [
            dcc.Graph(id='traffic-graph', figure=fig),
            html.Button('Refresh Data', id='refresh-button')
        ]
    elif pathname == '/dashboard/socialmedia':
        # Fetch social media data from the API
        social_media_response = requests.get("http://127.0.0.1:5000/api/socialmedia")
        social_media_data = pd.DataFrame(social_media_response.json())
        fig = px.bar(social_media_data, x="date", y=["likes", "retweets"], title="Twitter Engagements")
        return [
            dcc.Graph(id='socialmedia-graph', figure=fig),
            html.Button('Refresh Data', id='refresh-button')
        ]
    elif pathname == '/dashboard/facebook':
        # Fetch Facebook data from the API
        facebook_response = requests.get("http://127.0.0.1:5000/api/facebook")
        facebook_data = pd.DataFrame(facebook_response.json())
        fig = px.bar(facebook_data, x="date", y=["likes", "comments"], title="Facebook Engagements")
        return [
            dcc.Graph(id='facebook-graph', figure=fig),
            html.Button('Refresh Data', id='refresh-button')
        ]
    elif pathname == '/dashboard/instagram':
        # Fetch Instagram data from the API
        instagram_response = requests.get("http://127.0.0.1:5000/api/instagram")
        instagram_data = pd.DataFrame(instagram_response.json())
        fig = px.bar(instagram_data, x="date", y=["likes", "comments"], title="Instagram Engagements")
        return [
            dcc.Graph(id='instagram-graph', figure=fig),
            html.Button('Refresh Data', id='refresh-button')
        ]
    elif pathname == '/dashboard/conversions':
        fig = px.line(conversion_data, x="Month", y="Conversions", title="Conversion Rates")
        return [
            dcc.Graph(id='conversions-graph', figure=fig),
            html.Button('Refresh Data', id='refresh-button')
        ]
    elif pathname == '/dashboard/settings':
        return html.Div([
            html.H2("Settings"),
            html.Form(action="/settings", method="post", children=[
                html.Div([
                    html.Label("Google Analytics Key File Location:"),
                    html.Input(type="text", name="ga_key_file_location", value=KEY_FILE_LOCATION)
                ]),
                html.Div([
                    html.Label("Google Analytics View ID:"),
                    html.Input(type="text", name="ga_view_id", value=VIEW_ID)
                ]),
                html.Div([
                    html.Label("Twitter Consumer Key:"),
                    html.Input(type="text", name="twitter_consumer_key", value=TWITTER_CONSUMER_KEY)
                ]),
                html.Div([
                    html.Label("Twitter Consumer Secret:"),
                    html.Input(type="text", name="twitter_consumer_secret", value=TWITTER_CONSUMER_SECRET)
                ]),
                html.Div([
                    html.Label("Twitter Access Token:"),
                    html.Input(type="text", name="twitter_access_token", value=TWITTER_ACCESS_TOKEN)
                ]),
                html.Div([
                    html.Label("Twitter Access Token Secret:"),
                    html.Input(type="text", name="twitter_access_token_secret", value=TWITTER_ACCESS_TOKEN_SECRET)
                ]),
                html.Div([
                    html.Label("Twitter Handle:"),
                    html.Input(type="text", name="twitter_handle", value=settings['twitter']['handle'])
                ]),
                html.Div([
                    html.Label("Facebook Access Token:"),
                    html.Input(type="text", name="facebook_access_token", value=FACEBOOK_ACCESS_TOKEN)
                ]),
                html.Div([
                    html.Label("Instagram Access Token:"),
                    html.Input(type="text", name="instagram_access_token", value=INSTAGRAM_ACCESS_TOKEN)
                ]),
                html.Div([
                    html.Button("Save", type="submit")
                ])
            ])
        ])
    elif pathname == '/dashboard/profile':
        user_info = load_user(current_user.id)
        return html.Div([
            html.H2("User Profile"),
            html.P(f"Username: {user_info.username}"),
            html.Form(action="/profile/update", method="post", children=[
                html.Div([
                    html.Label("New Username:"),
                    html.Input(type="text", name="new_username", value=user_info.username)
                ]),
                html.Div([
                    html.Label("New Password:"),
                    html.Input(type="password", name="new_password")
                ]),
                html.Div([
                    html.Label("Confirm Password:"),
                    html.Input(type="password", name="confirm_password")
                ]),
                html.Div([
                    html.Button("Update Profile", type="submit")
                ])
            ])
        ])
    else:
        return html.Div([
            html.H2("Welcome to the Digital Marketing Dashboard!"),
            html.P("Use the menu to navigate through different sections.")
        ])

# Route for user profile update
@server.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    new_username = request.form['new_username']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']
    if new_password != confirm_password:
        flash('Passwords do not match')
        return redirect(url_for('display_page', pathname='/dashboard/profile'))
    hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
    with open('users.json', 'r') as f:
        users = json.load(f)
    users[current_user.id]['username'] = new_username
    users[current_user.id]['password'] = hashed_password
    with open('users.json', 'w') as f:
        json.dump(users, f)
    flash('Profile updated successfully')
    return redirect(url_for('index'))

# Registration route
@server.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash('Passwords do not match')
            return redirect(url_for('register'))
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user_id = str(len(users) + 1)
        users[user_id] = {'username': username, 'password': hashed_password}
        with open('users.json', 'w') as f:
            json.dump(users, f)
        flash('Registration successful')
        return redirect(url_for('login'))
    return render_template('register.html')

# Create the login page
@server.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with open('users.json', 'r') as f:
            users = json.load(f)
        for user_id, user_info in users.items():
            if user_info['username'] == username and bcrypt.check_password_hash(user_info['password'], password):
                user = User(id=user_id, username=username)
                login_user(user)
                return redirect(url_for('index'))
        flash('Invalid credentials')
    return render_template('login.html')

# Create the logout route
@server.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Route for the main page
@server.route('/')
@login_required
def index():
    return render_template('index.html')

# Route for saving settings
@server.route('/settings', methods=['POST'])
@login_required
def save_settings():
    global settings
    settings['google_analytics']['key_file_location'] = request.form['ga_key_file_location']
    settings['google_analytics']['view_id'] = request.form['ga_view_id']
    settings['twitter']['consumer_key'] = request.form['twitter_consumer_key']
    settings['twitter']['consumer_secret'] = request.form['twitter_consumer_secret']
    settings['twitter']['access_token'] = request.form['twitter_access_token']
    settings['twitter']['access_token_secret'] = request.form['twitter_access_token_secret']
    settings['twitter']['handle'] = request.form['twitter_handle']
    settings['facebook']['access_token'] = request.form['facebook_access_token']
    settings['instagram']['access_token'] = request.form['instagram_access_token']
    with open('settings.json', 'w') as f:
        json.dump(settings, f)
    return redirect(url_for('index'))

if __name__ == '__main__':
    server.run(debug=True)
