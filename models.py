from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    bride_first_name = db.Column(db.String(100))
    bride_last_name = db.Column(db.String(100))
    bride_email = db.Column(db.String(120))
    bride_parish = db.Column(db.String(200))
    groom_first_name = db.Column(db.String(100))
    groom_last_name = db.Column(db.String(100))
    groom_email = db.Column(db.String(120))
    groom_parish = db.Column(db.String(200))
    wedding_date = db.Column(db.Date)
    is_paid = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_couple_name(self):
        return f"{self.bride_first_name} & {self.groom_first_name}"

class Course(db.Model):
    __tablename__ = 'courses'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    duration = db.Column(db.String(50))
    price = db.Column(db.Numeric(10, 2), default=0)
    
class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    progress = db.Column(db.Integer, default=0)
    completed = db.Column(db.Boolean, default=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)