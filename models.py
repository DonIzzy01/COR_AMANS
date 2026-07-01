from extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import secrets
import string
import json


def _generate_registration_number():
    year = datetime.now(timezone.utc).replace(tzinfo=None).strftime('%Y')
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

    # ── BRIDE: Extended Personal ────────────────────────────────────────
    bride_dob = db.Column(db.Date, nullable=True)
    bride_phone = db.Column(db.String(30), nullable=True)
    bride_social_media = db.Column(db.String(500), nullable=True)
    bride_address = db.Column(db.Text, nullable=True)
    bride_parent_name = db.Column(db.String(200), nullable=True)
    bride_parent_address = db.Column(db.Text, nullable=True)
    bride_parents_alive = db.Column(db.String(20), nullable=True)
    bride_place_of_birth = db.Column(db.String(200), nullable=True)
    bride_occupation = db.Column(db.String(200), nullable=True)
    bride_education = db.Column(db.String(100), nullable=True)
    bride_num_siblings = db.Column(db.SmallInteger, nullable=True)
    bride_family_position = db.Column(db.String(50), nullable=True)

    # ── BRIDE: Religious ────────────────────────────────────────────────
    bride_is_catholic = db.Column(db.Boolean, nullable=True)
    bride_domicile_parish = db.Column(db.String(200), nullable=True)
    bride_years_domicile = db.Column(db.SmallInteger, nullable=True)
    bride_year_baptism = db.Column(db.SmallInteger, nullable=True)
    bride_year_first_communion = db.Column(db.SmallInteger, nullable=True)
    bride_year_confirmation = db.Column(db.SmallInteger, nullable=True)
    bride_previous_marriages = db.Column(db.Boolean, nullable=True)
    bride_church_switching = db.Column(db.Boolean, nullable=True)
    bride_parents_religion = db.Column(db.String(300), nullable=True)
    bride_church_society = db.Column(db.String(300), nullable=True)

    # ── BRIDE: Medical ──────────────────────────────────────────────────
    bride_blood_group = db.Column(db.String(10), nullable=True)
    bride_genotype = db.Column(db.String(10), nullable=True)
    bride_psychological_status = db.Column(db.String(200), nullable=True)
    bride_mental_illness_history = db.Column(db.Text, nullable=True)
    bride_phobias = db.Column(db.String(300), nullable=True)
    bride_allergies = db.Column(db.String(300), nullable=True)

    # ── GROOM: Extended Personal ────────────────────────────────────────
    groom_dob = db.Column(db.Date, nullable=True)
    groom_phone = db.Column(db.String(30), nullable=True)
    groom_social_media = db.Column(db.String(500), nullable=True)
    groom_address = db.Column(db.Text, nullable=True)
    groom_parent_name = db.Column(db.String(200), nullable=True)
    groom_parent_address = db.Column(db.Text, nullable=True)
    groom_parents_alive = db.Column(db.String(20), nullable=True)
    groom_place_of_birth = db.Column(db.String(200), nullable=True)
    groom_occupation = db.Column(db.String(200), nullable=True)
    groom_education = db.Column(db.String(100), nullable=True)
    groom_num_siblings = db.Column(db.SmallInteger, nullable=True)
    groom_family_position = db.Column(db.String(50), nullable=True)

    # ── GROOM: Religious ────────────────────────────────────────────────
    groom_is_catholic = db.Column(db.Boolean, nullable=True)
    groom_domicile_parish = db.Column(db.String(200), nullable=True)
    groom_years_domicile = db.Column(db.SmallInteger, nullable=True)
    groom_year_baptism = db.Column(db.SmallInteger, nullable=True)
    groom_year_first_communion = db.Column(db.SmallInteger, nullable=True)
    groom_year_confirmation = db.Column(db.SmallInteger, nullable=True)
    groom_previous_marriages = db.Column(db.Boolean, nullable=True)
    groom_church_switching = db.Column(db.Boolean, nullable=True)
    groom_parents_religion = db.Column(db.String(300), nullable=True)
    groom_church_society = db.Column(db.String(300), nullable=True)

    # ── GROOM: Medical ──────────────────────────────────────────────────
    groom_blood_group = db.Column(db.String(10), nullable=True)
    groom_genotype = db.Column(db.String(10), nullable=True)
    groom_psychological_status = db.Column(db.String(200), nullable=True)
    groom_mental_illness_history = db.Column(db.Text, nullable=True)
    groom_phobias = db.Column(db.String(300), nullable=True)
    groom_allergies = db.Column(db.String(300), nullable=True)

    # Profile
    profile_photo_url = db.Column(db.String(500), nullable=True)

    # Clerk integration
    clerk_user_id = db.Column(db.String(200), nullable=True, unique=True)

    # Status flags
    is_paid = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    force_password_change = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)

    # ── Security: account lockout ────────────────────────────────────────
    failed_login_attempts = db.Column(db.SmallInteger, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)

    # ── Course progress (0–100 per module slug, stored as JSON) ─────────
    module_progress = db.Column(db.Text, nullable=True)  # JSON: {"slug": pct, ...}

    # ── User preferences (theme, notifications, etc.) ───────────────────
    preferences = db.Column(db.Text, nullable=True)  # JSON

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relationships
    resources_uploaded = db.relationship('Resource', foreign_keys='Resource.uploaded_by', backref='uploader', lazy='dynamic')
    sessions_created = db.relationship('LiveSession', foreign_keys='LiveSession.created_by', backref='creator', lazy='dynamic')
    audit_logs = db.relationship('AuditLog', foreign_keys='AuditLog.user_id', backref='actor', lazy='dynamic')

    _PREF_DEFAULTS = {
        'theme': 'system',          # light | dark | system
        'email_notifications': True,
        'compact_mode': False,
    }

    def get_preferences(self):
        try:
            stored = json.loads(self.preferences) if self.preferences else {}
        except (ValueError, TypeError):
            stored = {}
        return {**self._PREF_DEFAULTS, **stored}

    def set_preference(self, key, value):
        prefs = self.get_preferences()
        prefs[key] = value
        self.preferences = json.dumps(prefs)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_couple_name(self):
        bride = self.bride_first_name or ''
        groom = self.groom_first_name or ''
        if bride and groom:
            return f"{bride} & {groom}"
        return bride or groom or self.email or ''

    def get_full_bride_name(self):
        return f"{self.bride_first_name or ''} {self.bride_last_name or ''}".strip()

    def get_full_groom_name(self):
        return f"{self.groom_first_name or ''} {self.groom_last_name or ''}".strip()

    def ensure_registration_number(self):
        if not self.registration_number:
            for _ in range(5):
                candidate = _generate_registration_number()
                if not User.query.filter_by(registration_number=candidate).first():
                    self.registration_number = candidate
                    return candidate
        return self.registration_number

    def is_locked(self):
        if self.locked_until and datetime.now(timezone.utc).replace(tzinfo=None) < self.locked_until:
            return True
        return False

    def get_module_progress(self):
        if not self.module_progress:
            return {}
        try:
            return json.loads(self.module_progress)
        except Exception:
            return {}

    def set_module_progress(self, slug, pct):
        data = self.get_module_progress()
        data[slug] = max(0, min(100, int(pct)))
        self.module_progress = json.dumps(data)

    def overall_progress(self):
        data = self.get_module_progress()
        if not data:
            return 0
        return round(sum(data.values()) / (len(FORMATION_MODULES) * 100) * 100)


# Formation module slugs (canonical list used for progress tracking)
FORMATION_MODULES = [
    "covenant-sacrament",
    "consent-freedom-liturgy",
    "unity-fidelity-indissolubility",
    "domestic-church-prayer",
    "openness-to-life",
    "communication-stewardship-mission",
]


class Resource(db.Model):
    """
    Admin-uploaded teaching material: YouTube/Vimeo videos or PDF documents.
    Admin can add, edit, or delete at any time.
    """
    __tablename__ = 'resources'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    # 'video' | 'document'
    resource_type = db.Column(db.String(20), nullable=False, default='video')

    # Video fields (YouTube or Vimeo URL — admin pastes the URL)
    video_url = db.Column(db.String(500))
    video_embed_id = db.Column(db.String(80))   # extracted from URL
    video_platform = db.Column(db.String(20))   # 'youtube' | 'vimeo'
    video_duration = db.Column(db.String(20))   # e.g. "45:32"

    # Document fields (PDF uploaded by admin)
    file_path = db.Column(db.String(500))       # relative: documents/filename.pdf
    file_name = db.Column(db.String(200))       # original filename shown to user
    file_size_kb = db.Column(db.Integer)

    # Categorisation
    module_slug = db.Column(db.String(100))     # which formation module
    category = db.Column(db.String(50))         # 'doctrine' | 'pastoral' | 'liturgy' | 'prayer' | 'general'
    tags = db.Column(db.String(300))            # comma-separated

    # Display
    sort_order = db.Column(db.Integer, default=0)
    is_published = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    thumbnail_url = db.Column(db.String(500))   # auto-set for YouTube; manual for others

    # Audit
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_embed_url(self):
        if self.resource_type != 'video' or not self.video_embed_id:
            return None
        if self.video_platform == 'youtube':
            return f"https://www.youtube.com/embed/{self.video_embed_id}?rel=0&modestbranding=1"
        if self.video_platform == 'vimeo':
            return f"https://player.vimeo.com/video/{self.video_embed_id}"
        return None

    def get_thumbnail(self):
        if self.thumbnail_url:
            return self.thumbnail_url
        if self.video_platform == 'youtube' and self.video_embed_id:
            return f"https://img.youtube.com/vi/{self.video_embed_id}/mqdefault.jpg"
        return None

    def get_file_url(self):
        if self.file_path:
            return f"/static/uploads/{self.file_path}"
        return None

    def get_size_display(self):
        if not self.file_size_kb:
            return ''
        if self.file_size_kb >= 1024:
            return f"{self.file_size_kb / 1024:.1f} MB"
        return f"{self.file_size_kb} KB"


class LiveSession(db.Model):
    """
    Scheduled live class. Admin creates with a Zoom/Meet link.
    After the session, admin can attach a recording URL.
    Admin can update any field at any time.
    """
    __tablename__ = 'live_sessions'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    host_name = db.Column(db.String(200))       # e.g. "Fr. Michael Obi"
    host_role = db.Column(db.String(100))       # e.g. "Parish Priest, Formation Director"

    # Schedule
    scheduled_at = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    timezone = db.Column(db.String(50), default='Africa/Lagos')

    # Meeting link (admin pastes Zoom/Meet/Teams/Jitsi URL)
    meeting_url = db.Column(db.String(500))
    meeting_id = db.Column(db.String(100))
    meeting_password = db.Column(db.String(100))
    platform = db.Column(db.String(30), default='zoom')  # zoom | meet | teams | jitsi

    # Recording (added after session completes)
    recording_url = db.Column(db.String(500))
    recording_embed_id = db.Column(db.String(80))
    recording_platform = db.Column(db.String(20))   # 'youtube' | 'vimeo'

    # Module link
    module_slug = db.Column(db.String(100))
    session_topic = db.Column(db.String(200))   # short topic displayed on card

    # Status: 'upcoming' | 'live' | 'completed' | 'cancelled'
    status = db.Column(db.String(20), default='upcoming')

    # Audit
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_recording_embed_url(self):
        if not self.recording_embed_id:
            return None
        if self.recording_platform == 'youtube':
            return f"https://www.youtube.com/embed/{self.recording_embed_id}?rel=0"
        if self.recording_platform == 'vimeo':
            return f"https://player.vimeo.com/video/{self.recording_embed_id}"
        return None

    def is_joinable(self):
        """True if session is within 15 min of start or currently live."""
        from datetime import timedelta
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        window_start = self.scheduled_at - timedelta(minutes=15)
        window_end = self.scheduled_at + timedelta(minutes=self.duration_minutes or 60)
        return window_start <= now <= window_end and self.status in ('upcoming', 'live')

    def status_label(self):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if self.status == 'cancelled':
            return 'Cancelled'
        if self.status == 'completed':
            return 'Recording Available' if self.recording_url else 'Completed'
        if self.is_joinable():
            return 'Join Now'
        if self.scheduled_at > now:
            return 'Upcoming'
        return 'Upcoming'


class AuditLog(db.Model):
    """
    Tamper-evident record of admin and system actions.
    Written by write_audit() helper in app.py — never deleted.
    """
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)    # e.g. 'resource.create'
    target_type = db.Column(db.String(50))                # 'resource' | 'session' | 'user'
    target_id = db.Column(db.Integer)
    detail = db.Column(db.Text)                           # JSON: extra context
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_detail(self):
        if not self.detail:
            return {}
        try:
            return json.loads(self.detail)
        except Exception:
            return {}


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
