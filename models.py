from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import secrets
import string


def _generate_registration_number():
    year = datetime.utcnow().strftime('%Y')
    suffix = ''.join(secrets.choice(string.digits) for _ in range(4))
    return f"COR-{year}-{suffix}"


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    registration_number = db.Column(db.String(20), unique=True, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    # Couple info
    bride_first_name = db.Column(db.String(100))
    bride_last_name = db.Column(db.String(100))
    bride_email = db.Column(db.String(120))
    bride_parish = db.Column(db.String(200))
    groom_first_name = db.Column(db.String(100))
    groom_last_name = db.Column(db.String(100))
    groom_email = db.Column(db.String(120))
    groom_parish = db.Column(db.String(200))
    wedding_date = db.Column(db.Date)

    # Profile
    profile_photo_url = db.Column(db.String(500), nullable=True)

    # Clerk integration (populated when Clerk is configured)
    clerk_user_id = db.Column(db.String(200), nullable=True, unique=True)

    # Status flags
    is_paid = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    force_password_change = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_couple_name(self):
        bride = self.bride_first_name or ''
        groom = self.groom_first_name or ''
        if bride and groom:
            return f"{bride} & {groom}"
        return bride or groom or self.email

    def get_full_bride_name(self):
        return f"{self.bride_first_name or ''} {self.bride_last_name or ''}".strip()

    def get_full_groom_name(self):
        return f"{self.groom_first_name or ''} {self.groom_last_name or ''}".strip()

    def ensure_registration_number(self):
        if not self.registration_number:
            # Try up to 5 times to get a unique number
            for _ in range(5):
                candidate = _generate_registration_number()
                if not User.query.filter_by(registration_number=candidate).first():
                    self.registration_number = candidate
                    return candidate
        return self.registration_number


class Course(db.Model):
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    duration = db.Column(db.String(50))
    price = db.Column(db.Numeric(10, 2), default=50000)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Enrollment(db.Model):
    __tablename__ = 'enrollments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    progress = db.Column(db.Integer, default=0)
    completed = db.Column(db.Boolean, default=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
