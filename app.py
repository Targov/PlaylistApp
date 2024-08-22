from flask import Flask, render_template, redirect, url_for, session, request
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from datetime import timedelta

# Initialize the Flask application
app = Flask(__name__)

# Set secret key for session management
app.secret_key = 'your_secret_key'

# Configure the SQLite database URI
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///favplaylist.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Set session settings
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=15)  # Session timeout
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True if using HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Change to 'Strict' if needed

# Initialize the SQLAlchemy database object
db = SQLAlchemy(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Define the User model
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    songs = db.relationship('Song', order_by='Song.id', back_populates='user')
    sent_friendships = db.relationship('Friendship', foreign_keys='Friendship.user_id', back_populates='sender')
    received_friendships = db.relationship('Friendship', foreign_keys='Friendship.friend_id', back_populates='receiver')

# Define the Song model
class Song(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    artist = db.Column(db.String(100), nullable=False)
    youtube_url = db.Column(db.String(200), nullable=True)  
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', back_populates='songs')

# Define the Friendship model
class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sender = db.relationship('User', foreign_keys=[user_id], back_populates='sent_friendships')
    receiver = db.relationship('User', foreign_keys=[friend_id], back_populates='received_friendships')

    def __repr__(self):
        return f'<Friendship user_id={self.user_id} friend_id={self.friend_id}>'

# Home route
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Fetch songs for the current user
    songs = Song.query.filter_by(user_id=session['user_id']).all()
    return render_template('home.html', songs=songs)

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    error_message = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username  # Save username to session
            return redirect(url_for('home'))
        else:
            error_message = 'Invalid credentials'

    return render_template('login.html', error_message=error_message)

# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    error_message = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            error_message = 'Username already exists. Please choose a different one.'
        else:
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('register.html', error_message=error_message)

# Add song route
@app.route('/add_song', methods=['POST'])
def add_song():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    song_name = request.form.get('song_name', '')
    artist = request.form.get('artist', '')
    youtube_url = request.form.get('youtube_url', '')
    new_song = Song(name=song_name, artist=artist, user_id=session['user_id'], youtube_url=youtube_url)
    db.session.add(new_song)
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/edit_song/<int:song_id>', methods=['GET'])
def edit_song(song_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    song = Song.query.get_or_404(song_id)
    if song.user_id != session['user_id']:
        return redirect(url_for('home'))

    return render_template('edit_song.html', song=song)


# Update song route
@app.route('/update_song/<int:song_id>', methods=['POST'])
def update_song(song_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    song = Song.query.get_or_404(song_id)
    if song.user_id != session['user_id']:
        return redirect(url_for('home'))

    song.name = request.form['song_name']
    song.artist = request.form['artist']
    song.youtube_url = request.form['youtube_url']

    db.session.commit()
    return redirect(url_for('home'))

# Logout route
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.permanent = False
    response = redirect(url_for('login'))
    response.set_cookie('session', '', expires=0)
    return response

# Add a route to view friends
@app.route('/friends')
def friends():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    friends = [f.receiver for f in user.received_friendships]
    return render_template('friends.html', friends=friends)

# Add a route to add friends
@app.route('/add_friend', methods=['POST'])
def add_friend():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    friend_username = request.form.get('friend_username')
    friend = User.query.filter_by(username=friend_username).first()
    if friend and friend.id != session['user_id']:
        existing_friendship = Friendship.query.filter_by(user_id=session['user_id'], friend_id=friend.id).first()
        if not existing_friendship:
            new_friendship = Friendship(user_id=session['user_id'], friend_id=friend.id)
            db.session.add(new_friendship)
            db.session.commit()
    
    return redirect(url_for('friends'))

# Main block
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
