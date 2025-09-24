from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_
from flask_socketio import SocketIO, emit, join_room, leave_room
import datetime
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

db_uri = 'postgresql://postgres:rudrark12@localhost/sync_db'
secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = secret_key

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

online_users = {}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy=True)
    def __repr__(self):
        return f'<User {self.username}>'
    
class DailyAnalytics(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    new_users_count = db.Column(db.Integer, default=0)
    messages_sent_count = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<Analytics for {self.date}>'

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    is_media = db.Column(db.Boolean, default=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.now)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    def __repr__(self):
        return f'<Message {self.id}>'

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        user_by_email = User.query.filter_by(email=email).first()
        if user_by_email:
            flash("Email address already exists.", "error")
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, email=email, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        socketio.emit('new_user_joined', {
            'id': new_user.id,
            'username': new_user.username
        }, broadcast=True)

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid email or password.", "error")
            return redirect(url_for('login'))
        session['user_id'] = user.id
        session['username'] = user.username
        return redirect(url_for('chat'))
    return render_template('login.html')

@app.route('/chat')
def chat():
    if 'user_id' not in session:
        flash("You need to be logged in to see this page.", "error")
        return redirect(url_for('login'))

    current_user_id = session['user_id']
    all_users = User.query.filter(User.id != current_user_id).all()

    unread_counts = {}
    for user in all_users:
        count = Message.query.filter_by(
            sender_id=user.id, 
            receiver_id=current_user_id, 
            is_read=False
        ).count()
        unread_counts[user.id] = count

    return render_template('chat.html', all_users=all_users, unread_counts=unread_counts)
    
@app.route('/get_messages/<int:recipient_id>')
def get_messages(recipient_id):
    if 'user_id' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    current_user_id = session['user_id']
    
    Message.query.filter_by(
        sender_id=recipient_id, 
        receiver_id=current_user_id, 
        is_read=False
    ).update({'is_read': True})
    db.session.commit()

    messages = Message.query.filter(
        or_(
            (Message.sender_id == current_user_id) & (Message.receiver_id == recipient_id),
            (Message.sender_id == recipient_id) & (Message.receiver_id == current_user_id)
        )
    ).order_by(Message.timestamp.asc()).all()
    message_list = [{"sender_id": msg.sender_id, "content": msg.content, "is_media": msg.is_media, "timestamp": msg.timestamp.strftime("%b %d, %H:%M")} for msg in messages]
    return jsonify(message_list)

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

@app.route('/api/users')
def api_users():
    all_users = User.query.all()
    user_list = [
        {'id': user.id, 'username': user.username, 'email': user.email, 'created_at': user.created_at.isoformat()}for user in all_users
    ]
    return jsonify(user_list)

@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        current_user_id = session['user_id']
        online_users[current_user_id] = request.sid
        print(f"User {current_user_id} connected with sid {request.sid}")
        emit('online_status_update', list(online_users.keys()), broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    for user_id, sid in list(online_users.items()):
        if sid == request.sid:
            del online_users[user_id]
            print(f"User {user_id} disconnected.")
            emit('online_status_update', list(online_users.keys()), broadcast=True)
            break
        
@socketio.on('private_message')
def handle_private_message(data):
    recipient_id = data['recipient_id']
    message_content = data['message']
    sender_id = session['user_id']
    
    new_message = Message(
        sender_id=sender_id,
        receiver_id=recipient_id,
        content=message_content
    )
    db.session.add(new_message)
    db.session.commit()

    message_data = {
        "sender_id": sender_id,
        "content": new_message.content,
        "timestamp": new_message.timestamp.strftime("%b %d, %H:%M")
    }
    
    recipient_sid = online_users.get(recipient_id)
    if recipient_sid:
        emit('new_message', message_data, room=recipient_sid)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, host='0.0.0.0', debug=True)