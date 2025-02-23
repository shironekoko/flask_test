from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash  # เพิ่มระบบเข้ารหัสรหัสผ่าน
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)

class SharedNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    note_id = db.Column(db.Integer, db.ForeignKey('note.id'), nullable=False)
    shared_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    note = db.relationship('Note', backref='shared_notes', lazy=True)
    shared_user = db.relationship('User', backref='shared_notes', lazy=True)

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('notes', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def home():
    return redirect(url_for('my_notes'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose another one.', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        user = User(username=username, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('my_notes'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html')

@app.route('/changepassword', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        current_user.username = username
        current_user.password = generate_password_hash(password, method='pbkdf2:sha256')
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('changepassword'))
    return render_template('changepassword.html')

@app.route('/create_note', methods=['GET', 'POST'])
@login_required
def create_note():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        category = request.form.get('category')
        
        note = Note(title=title, content=content, category=category, user_id=current_user.id)
        db.session.add(note)
        db.session.commit()
        flash('Note has been created!', 'success')
        return redirect(url_for('my_notes'))
    
    return render_template('create_note.html')

@app.route('/my_notes')
@login_required
def my_notes():
    notes = Note.query.filter_by(user_id=current_user.id).all()
    return render_template('my_notes.html', notes=notes)

@app.route('/statistics')
@login_required
def statistics():
    total_notes = Note.query.filter_by(user_id=current_user.id).count()
    category_counts = db.session.query(Note.category, db.func.count(Note.id)) \
        .filter_by(user_id=current_user.id) \
        .group_by(Note.category).all()
    
    # เตรียมข้อมูลสำหรับกราฟ
    categories = [category[0] for category in category_counts]
    counts = [category[1] for category in category_counts]

    return render_template('statistics.html', total_notes=total_notes, category_counts=category_counts, categories=categories, counts=counts)

@app.route('/edit_note/<int:note_id>', methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        flash('You do not have permission to edit this note.', 'danger')
        return redirect(url_for('my_notes'))
    
    if request.method == 'POST':
        note.title = request.form.get('title')
        note.content = request.form.get('content')
        note.category = request.form.get('category')
        db.session.commit()
        flash('Note has been updated!', 'success')
        return redirect(url_for('my_notes'))
    
    return render_template('edit_note.html', note=note)

@app.route('/delete_note/<int:note_id>', methods=['POST'])
@login_required
def delete_note(note_id):
    # หโน้ตที่ต้องการลบ
    note = Note.query.get_or_404(note_id)

    # ตรวจสอบว่าโน้ตนี้เป็นของผู้ใช้ที่ล็อกอินอยู่หรือไม่
    if note.user_id != current_user.id:
        flash('You do not have permission to delete this note.', 'danger')
        return redirect(url_for('my_notes'))

    # ลบโน้ตจากฐานข้อมูล
    db.session.delete(note)
    db.session.commit()

    flash('Your note has been deleted.', 'success')
    return redirect(url_for('my_notes'))

@app.route('/category/<string:category>')
@login_required
def notes_by_category(category):
    # ตรวจสอบว่า category ไม่ว่างเปล่า
    if not category:
        flash('Invalid category.', 'danger')
        return redirect(url_for('my_notes'))

    notes = Note.query.filter_by(user_id=current_user.id, category=category).all()
    if not notes:
        flash(f'No notes found in the {category} category.', 'info')
    
    return render_template('category_notes.html', notes=notes, category=category)

@app.route('/share_note/<int:note_id>', methods=['GET', 'POST'])
@login_required
def share_note(note_id):
    note = Note.query.get_or_404(note_id)
    
    # ตรวจสอบว่าโน้ตนี้เป็นของผู้ใช้ที่ล็อกอินอยู่
    if note.user_id != current_user.id:
        flash('You do not have permission to share this note.', 'danger')
        return redirect(url_for('my_notes'))
    
    if request.method == 'POST':
        # รับ ID ของผู้ใช้ที่ต้องการแชร์โน้ต
        shared_user_id = request.form.get('shared_user_id')
        
        # ตรวจสอบว่าผู้ใช้ที่แชร์อยู่ในฐานข้อมูลหรือไม่
        shared_user = User.query.get(shared_user_id)
        if shared_user:
            shared_note = SharedNote(note_id=note.id, shared_user_id=shared_user.id)
            db.session.add(shared_note)
            db.session.commit()
            flash(f'Note shared with {shared_user.username}!', 'success')
            return redirect(url_for('shared_notes'))
        else:
            flash('User not found.', 'danger')
    
    users = User.query.all()  # เลือกผู้ใช้ทั้งหมดสำหรับการแชร์
    return render_template('share_note.html', note=note, users=users)

@app.route('/shared_notes')
@login_required
def shared_notes():
    # ค้นหาทุกโน้ตที่ถูกแชร์ไปยังผู้ใช้ที่ล็อกอิน
    shared_notes = SharedNote.query.filter_by(shared_user_id=current_user.id).all()
    notes = [shared_note.note for shared_note in shared_notes]
    return render_template('shared_notes.html', notes=notes)

@app.route('/report', methods=['GET'])
@login_required
def report():
    today = datetime.today()

    # สำหรับรายงานรายวัน
    daily_notes = Note.query.filter(
        Note.timestamp >= today.replace(hour=0, minute=0, second=0, microsecond=0),
        Note.timestamp < today.replace(hour=23, minute=59, second=59, microsecond=999999),
        Note.user_id == current_user.id
    ).all()

    # สำหรับรายงานรายสัปดาห์
    week_start = today - timedelta(days=today.weekday())  # เริ่มต้นวันจันทร์ของสัปดาห์นี้
    week_end = week_start + timedelta(days=6)  # วันอาทิตย์ของสัปดาห์นี้
    weekly_notes = Note.query.filter(
        Note.timestamp >= week_start,
        Note.timestamp <= week_end,
        Note.user_id == current_user.id
    ).all()
    return render_template('report.html', daily_notes=daily_notes, weekly_notes=weekly_notes)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    if not os.path.exists('site.db'):
        with app.app_context():
            db.create_all()
    app.run(debug=True)
