import os
import re
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import Lock

from flask import (Flask, abort, flash, redirect, render_template,
                   request, session, url_for, jsonify)
from dotenv import load_dotenv
from config import Config
from extensions import db, login_manager, mail
from models import User, Course, Enrollment
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from functools import lru_cache, wraps
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

RATE_LIMIT_STORE = defaultdict(list)
RATE_LIMIT_LOCK = Lock()
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SESSION_IDLE_TIMEOUT = 20 * 60

# Initialize extensions
db.init_app(app)
mail.init_app(app)
login_manager.init_app(app)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_globals():
    pub_key = app.config.get('CLERK_PUBLISHABLE_KEY', '')
    from clerk_auth import _frontend_api_from_key
    return {
        "csrf_token": generate_csrf_token,
        "idempotency_key": issue_idempotency_key,
        "clerk_enabled": app.config.get('CLERK_ENABLED', False),
        "clerk_publishable_key": pub_key,
        "clerk_frontend_api": _frontend_api_from_key(pub_key) if pub_key else '',
    }


@login_manager.unauthorized_handler
def handle_unauthorized():
    flash("Please log in to continue.", "warning")
    return redirect(url_for("login"))


def init_db():
    """Create tables. Called by entrypoint.sh (once, before workers fork) or by python app.py."""
    with app.app_context():
        db.create_all()


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)

# ──────────────────────────────────────────────────
#  Security helpers
# ──────────────────────────────────────────────────

def generate_reference(user_id):
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"COR-{user_id}-{timestamp}-{secrets.token_hex(4)}"


def generate_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def issue_idempotency_key(namespace):
    tokens = session.setdefault("_idempotency_tokens", {})
    if namespace not in tokens:
        tokens[namespace] = secrets.token_urlsafe(24)
        session.modified = True
    return tokens[namespace]


def check_idempotency(namespace):
    submitted = request.form.get("idempotency_key")
    tokens = session.setdefault("_idempotency_tokens", {})
    used_tokens = session.setdefault("_used_idempotency_tokens", {})
    if submitted and used_tokens.get(namespace) == submitted:
        return "duplicate"
    expected = tokens.get(namespace)
    if not submitted or not expected or not secrets.compare_digest(submitted, expected):
        return "invalid"
    used_tokens[namespace] = submitted
    tokens[namespace] = secrets.token_urlsafe(24)
    session.modified = True
    return "fresh"


def validate_csrf():
    session_token = session.get("_csrf_token")
    request_token = (
        request.form.get("csrf_token")
        or request.headers.get("X-CSRF-Token")
        or request.headers.get("X-CSRFToken")
    )
    return bool(session_token and request_token and secrets.compare_digest(session_token, request_token))


def csrf_protect(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == "POST" and not validate_csrf():
            flash("Your session token is invalid or expired. Please try again.", "error")
            return redirect(url_for(get_safe_post_redirect_target()))
        return f(*args, **kwargs)
    return decorated_function


def get_safe_post_redirect_target():
    if request.endpoint == "register":
        return "register"
    if request.endpoint == "login":
        return "login"
    if request.endpoint and request.endpoint.startswith("admin"):
        if current_user.is_authenticated and current_user.is_admin:
            return "admin_dashboard"
        return "landing"
    if current_user.is_authenticated:
        return "dashboard" if getattr(current_user, "is_paid", False) else "payment"
    return "landing"


def get_client_ip():
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "unknown"


def rate_limit(limit, window_seconds, scope="global"):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            now = time.time()
            key = f"{scope}:{request.endpoint}:{get_client_ip()}"
            with RATE_LIMIT_LOCK:
                recent_hits = [t for t in RATE_LIMIT_STORE[key] if t > now - window_seconds]
                RATE_LIMIT_STORE[key] = recent_hits
                if len(recent_hits) >= limit:
                    retry_after = int(window_seconds - (now - recent_hits[0]))
                    flash("Too many requests. Please wait a moment and try again.", "error")
                    response = redirect(request.referrer or url_for("landing"))
                    response.headers["Retry-After"] = str(max(retry_after, 1))
                    return response
                RATE_LIMIT_STORE[key].append(now)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in to access the admin panel.", "warning")
            return redirect(url_for("login"))
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def allowed_image(filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in app.config['ALLOWED_IMAGE_EXTENSIONS']


# ──────────────────────────────────────────────────
#  Security headers + session timeout
# ──────────────────────────────────────────────────

@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

    clerk_extra = ""
    if app.config.get('CLERK_ENABLED'):
        clerk_extra = (
            " https://clerk.accounts.dev https://*.clerk.accounts.dev"
            " https://*.clerk.com"
        )

    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        f"script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com "
        f"https://cdnjs.cloudflare.com https://cdn.jsdelivr.net{clerk_extra}; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com "
        f"https://fonts.googleapis.com{clerk_extra}; "
        "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com data:; "
        f"img-src 'self' data: blob:{clerk_extra}; "
        f"connect-src 'self'{clerk_extra}; "
        f"frame-src 'self'{clerk_extra}; "
        "form-action 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'none';"
    )

    sensitive_paths = {"/login", "/register", "/payment", "/dashboard", "/change-password", "/logout"}
    if request.path in sensitive_paths or request.path.startswith("/admin"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    elif request.method == "GET" and request.path in {"/", "/courses", "/about"}:
        response.headers["Cache-Control"] = "public, max-age=300"
    return response


@app.before_request
def enforce_session_timeout():
    if not current_user.is_authenticated:
        session.pop("last_activity", None)
        return None
    now = int(time.time())
    last_activity = session.get("last_activity")
    if last_activity and now - last_activity > SESSION_IDLE_TIMEOUT:
        logout_user()
        session.clear()
        flash("Your session ended after a period of inactivity. Please log in again.", "warning")
        return redirect(url_for("login"))
    session["last_activity"] = now
    session.modified = True
    return None


# ──────────────────────────────────────────────────
#  Email helpers
# ──────────────────────────────────────────────────

def send_email(subject, recipients, html_body, text_body=None):
    """Send an email if mail is configured; otherwise silently skip."""
    if not app.config.get('MAIL_ENABLED'):
        return
    try:
        msg = Message(subject, recipients=recipients)
        msg.html = html_body
        if text_body:
            msg.body = text_body
        mail.send(msg)
    except Exception as exc:
        app.logger.warning("Email send failed: %s", exc)


def send_welcome_email(user):
    html = f"""
    <div style="font-family:Georgia,serif;max-width:600px;margin:auto;padding:40px;background:#fff;">
      <h2 style="color:#1B4332;">Welcome to COR AMANS, {user.get_couple_name()}!</h2>
      <p style="color:#334155;line-height:1.7;">
        Your registration is confirmed. Your couple reference number is
        <strong style="color:#166534;">{user.registration_number}</strong>.
      </p>
      <p style="color:#334155;line-height:1.7;">
        Complete your payment to unlock your dashboard, live classes, and formation materials.
      </p>
      <a href="{app.config['APP_URL']}/payment"
         style="display:inline-block;margin-top:16px;padding:12px 28px;
                background:#1B4332;color:#fff;border-radius:8px;text-decoration:none;font-weight:600;">
        Complete Payment
      </a>
      <p style="margin-top:32px;color:#64748b;font-size:14px;">
        May God bless your marriage preparation.<br>
        <em>The COR AMANS Team</em>
      </p>
    </div>
    """
    send_email(
        subject="Welcome to COR AMANS – Registration Confirmed",
        recipients=[user.email],
        html_body=html,
    )


def send_payment_confirmation_email(user):
    html = f"""
    <div style="font-family:Georgia,serif;max-width:600px;margin:auto;padding:40px;background:#fff;">
      <h2 style="color:#1B4332;">Payment Confirmed, {user.get_couple_name()}!</h2>
      <p style="color:#334155;line-height:1.7;">
        Your payment has been received. Your dashboard, live classes, and all formation
        materials are now unlocked.
      </p>
      <p style="color:#334155;">Reference: <strong style="color:#166534;">{user.registration_number}</strong></p>
      <a href="{app.config['APP_URL']}/dashboard"
         style="display:inline-block;margin-top:16px;padding:12px 28px;
                background:#1B4332;color:#fff;border-radius:8px;text-decoration:none;font-weight:600;">
        Open Your Dashboard
      </a>
      <p style="margin-top:32px;color:#64748b;font-size:14px;">
        <em>The COR AMANS Team</em>
      </p>
    </div>
    """
    send_email(
        subject="COR AMANS – Payment Confirmed",
        recipients=[user.email],
        html_body=html,
    )


# ──────────────────────────────────────────────────
#  Static data helpers (cached)
# ──────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_core_course_catalog():
    return [
        {
            "slug": "covenant-sacrament",
            "title": "The Covenant and Sacrament of Matrimony",
            "duration": "2 weeks",
            "format": "Doctrine seminar + mentor discussion",
            "summary": "Study Catholic marriage as a covenant ordered to the good of the spouses and the procreation and education of children, raised by Christ to a sacrament between the baptized.",
            "highlights": [
                "Marriage as a lifelong covenant and vocation",
                "The grace of the sacrament for Christian spouses",
                "Why the Church prepares couples before the liturgy",
            ],
            "refs": "CCC 1601, 1638–1642, 1660–1661",
            "level": "Foundation",
        },
        {
            "slug": "consent-liturgical-celebration",
            "title": "Consent, Freedom, and the Wedding Liturgy",
            "duration": "1 week",
            "format": "Guided workshop",
            "summary": "Focus on matrimonial consent, readiness, freedom, and the public liturgical nature of Catholic marriage.",
            "highlights": [
                "What valid consent means in the Catholic tradition",
                "Freedom, intention, and mature readiness",
                "How the Church celebrates marriage within the community",
            ],
            "refs": "CCC 1625–1632, 1662–1663",
            "level": "Core preparation",
        },
        {
            "slug": "unity-fidelity-indissolubility",
            "title": "Unity, Fidelity, and Indissolubility",
            "duration": "2 weeks",
            "format": "Case-study classroom",
            "summary": "Explore the Church's teaching that conjugal love is faithful, exclusive, and lifelong, reflecting Christ's love for the Church.",
            "highlights": [
                "Why marriage is exclusive and faithful",
                "The permanence of the marriage bond",
                "How the Church supports couples in difficult seasons",
            ],
            "refs": "CCC 1643–1651, 1664–1665",
            "level": "Formation",
        },
        {
            "slug": "domestic-church-prayer",
            "title": "The Domestic Church and Prayer in Family Life",
            "duration": "1 week",
            "format": "Prayer practicum + live session",
            "summary": "Build habits of prayer, sacramental life, and Christian witness in the home as the domestic church.",
            "highlights": [
                "Shared prayer in married life",
                "Faith formation within the home",
                "The home as a school of charity and virtue",
            ],
            "refs": "CCC 1655–1658, 1666",
            "level": "Spiritual life",
        },
        {
            "slug": "openness-to-life",
            "title": "Openness to Life and Responsible Parenthood",
            "duration": "1 week",
            "format": "Lecture + pastoral Q&A",
            "summary": "Review Catholic teaching on fruitfulness, the dignity of children, and responsible parenthood in a way that honors conscience formed by the Church.",
            "highlights": [
                "Children as a gift within marriage",
                "Service to life and parental responsibility",
                "Pastoral formation for honest conversations as a couple",
            ],
            "refs": "CCC 1652–1654, 1664",
            "level": "Pastoral guidance",
        },
        {
            "slug": "communication-stewardship-mission",
            "title": "Communication, Stewardship, and Mission",
            "duration": "2 weeks",
            "format": "Applied classroom track",
            "summary": "Apply Catholic principles to communication, finances, conflict resolution, hospitality, and service in parish life.",
            "highlights": [
                "Faithful communication and mutual respect",
                "Stewardship of money, time, and responsibilities",
                "Serving the wider Church together",
            ],
            "refs": "Built from the vocation of spouses to communion, charity, and witness.",
            "level": "Applied practice",
        },
    ]


@lru_cache(maxsize=1)
def get_live_classroom_schedule():
    return [
        {
            "title": "Live Doctrine Class: Matrimony in God's Plan",
            "time": "Tuesday, 7:00 PM",
            "mode": "Live video classroom",
            "host": "Fr. Michael and the parish formation team",
            "status": "Upcoming",
            "cta": "Room opens 15 minutes before class",
            "focus": "Marriage as covenant, sacrament, and vocation",
            "room": "Room A1",
            "join_label": "Join live room",
        },
        {
            "title": "Couples Mentoring Circle",
            "time": "Thursday, 6:30 PM",
            "mode": "Guided small-group meeting",
            "host": "Marriage mentor couples",
            "status": "Open this week",
            "cta": "Discuss prayer, communication, and home routines",
            "focus": "Prayer rhythm, emotional honesty, and home culture",
            "room": "Mentor Circle B",
            "join_label": "Open mentor room",
        },
        {
            "title": "Assessment Review and Q&A",
            "time": "Saturday, 10:00 AM",
            "mode": "Interactive classroom",
            "host": "Course facilitator",
            "status": "Monthly",
            "cta": "Bring questions from your current module",
            "focus": "Assessment feedback and pastoral clarification",
            "room": "Review Hall",
            "join_label": "View class details",
        },
    ]


def get_classroom_stream(user):
    return [
        {
            "type": "assignment",
            "badge": "Due this week",
            "title": "Reflection: Covenant, Consent, and Readiness",
            "description": "Write a shared reflection on vocation, freedom, and the promises you are preparing to make.",
            "meta": "Due before your next mentor meeting",
            "action": "Open reflection guide",
        },
        {
            "type": "discussion",
            "badge": "Community board",
            "title": "Discussion Board: Building a Domestic Church",
            "description": "Share one realistic prayer rhythm you want to begin as a couple this month.",
            "meta": "Classroom discussion space",
            "action": "View discussion prompt",
        },
        {
            "type": "resource",
            "badge": "Downloadable",
            "title": "Resource Pack: Catholic Marriage Toolkit",
            "description": "Includes a prayer plan, meeting checklist, household stewardship guide, and family mission worksheet.",
            "meta": "Available to all enrolled couples",
            "action": "Download materials",
        },
        {
            "type": "meeting",
            "badge": "Private support",
            "title": "Pastoral Check-In",
            "description": f"Schedule a short meeting for {user.get_couple_name()} with the formation team if you need support.",
            "meta": "Private support session",
            "action": "Request meeting",
        },
    ]


def get_dashboard_milestones(user):
    return [
        {
            "label": "Registration",
            "status": "Completed",
            "complete": True,
            "note": f"Couple reference: {user.registration_number or 'Assigning…'}",
        },
        {
            "label": "Course Access",
            "status": "Unlocked" if user.is_paid else "Waiting for payment",
            "complete": user.is_paid,
            "note": "Dashboard, live classes, and assessments open after payment",
        },
        {
            "label": "Live Classroom",
            "status": "Scheduled" if user.is_paid else "Pending access",
            "complete": user.is_paid,
            "note": "Weekly teaching and mentor sessions",
        },
        {
            "label": "Certificate Path",
            "status": "In progress" if user.is_paid else "Locked",
            "complete": False,
            "note": "Completion follows module work, meetings, and assessment review",
        },
    ]


def get_doctrine_principles():
    return [
        {
            "title": "Marriage as Covenant",
            "description": "Catholic marriage is a covenant for the good of the spouses and the gift of family life.",
            "refs": "CCC 1601",
        },
        {
            "title": "Grace of the Sacrament",
            "description": "Christ strengthens baptized spouses with sacramental grace for daily married life.",
            "refs": "CCC 1638–1642",
        },
        {
            "title": "Fidelity and Indissolubility",
            "description": "Christian marriage is faithful, exclusive, and lifelong in imitation of Christ's love.",
            "refs": "CCC 1643–1651",
        },
        {
            "title": "Domestic Church",
            "description": "The home becomes a place of prayer, virtue, hospitality, and witness.",
            "refs": "CCC 1655–1666",
        },
    ]


def get_classroom_features():
    return [
        {
            "title": "Live formation classes",
            "description": "Weekly classroom meetings with doctrine teaching, pastoral guidance, and live questions.",
            "icon": "fa-video",
        },
        {
            "title": "Couple assignments",
            "description": "Shared reflections, assessments, and practical exercises completed together.",
            "icon": "fa-book-open-reader",
        },
        {
            "title": "Mentor support",
            "description": "Structured check-ins with parish mentors and pastoral follow-up when couples need help.",
            "icon": "fa-people-group",
        },
        {
            "title": "Sacramental pathway",
            "description": "Every step prepares couples for the liturgy and the vocation of Christian family life.",
            "icon": "fa-church",
        },
    ]


# ──────────────────────────────────────────────────
#  Public routes
# ──────────────────────────────────────────────────

@app.route("/health")
def health_check():
    return jsonify({"status": "ok"}), 200


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/courses")
def courses():
    return render_template(
        "courses.html",
        course_catalog=get_core_course_catalog(),
        doctrine_principles=get_doctrine_principles(),
        classroom_features=get_classroom_features(),
        live_sessions=get_live_classroom_schedule(),
    )


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/email-verified")
def email_verified():
    from datetime import date
    return render_template("email_verified.html", verified_date=date.today().strftime('%b %d, %Y'))


# ──────────────────────────────────────────────────
#  Auth routes
# ──────────────────────────────────────────────────

@app.route("/register", methods=["GET", "POST"])
@rate_limit(limit=8, window_seconds=15 * 60, scope="auth")
@csrf_protect
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard") if current_user.is_paid else url_for("payment"))

    if request.method == "POST":
        idempotency_state = check_idempotency("register")
        if idempotency_state == "duplicate":
            flash("This registration was already submitted.", "info")
            return redirect(url_for("payment" if current_user.is_authenticated else "login"))
        if idempotency_state == "invalid":
            flash("Your registration form expired. Please try again.", "error")
            return redirect(url_for("register"))

        def _fg(key):
            return request.form.get(key, "").strip()

        def _date(key):
            val = _fg(key)
            try:
                return datetime.strptime(val, '%Y-%m-%d').date() if val else None
            except ValueError:
                return None

        def _int(key):
            val = _fg(key)
            try:
                return int(val) if val else None
            except ValueError:
                return None

        def _bool(key):
            val = _fg(key).lower()
            if val == 'yes':
                return True
            if val == 'no':
                return False
            return None

        # ── Core required fields ──────────────────────────────────────
        bride_first = _fg("bride_first_name")
        bride_last  = _fg("bride_last_name")
        bride_email = _fg("bride_email").lower()
        bride_parish = _fg("bride_parish")
        groom_first = _fg("groom_first_name")
        groom_last  = _fg("groom_last_name")
        groom_email = _fg("groom_email").lower()
        groom_parish = _fg("groom_parish")
        password = _fg("password")
        confirm_password = _fg("confirm_password")
        accepted_terms = request.form.get("terms") == "on"

        # ── Extended bride personal ───────────────────────────────────
        bride_dob           = _date("bride_dob")
        bride_phone         = _fg("bride_phone")
        bride_social_media  = _fg("bride_social_media")
        bride_address       = _fg("bride_address")
        bride_parent_name   = _fg("bride_parent_name")
        bride_parent_address= _fg("bride_parent_address")
        bride_parents_alive = _fg("bride_parents_alive")
        bride_place_of_birth= _fg("bride_place_of_birth")
        bride_occupation    = _fg("bride_occupation")
        bride_education     = _fg("bride_education")
        bride_num_siblings  = _int("bride_num_siblings")
        bride_family_position= _fg("bride_family_position")

        # ── Bride religious ───────────────────────────────────────────
        bride_is_catholic         = _bool("bride_is_catholic")
        bride_domicile_parish     = _fg("bride_domicile_parish")
        bride_years_domicile      = _int("bride_years_domicile")
        bride_year_baptism        = _int("bride_year_baptism")
        bride_year_first_communion= _int("bride_year_first_communion")
        bride_year_confirmation   = _int("bride_year_confirmation")
        bride_previous_marriages  = _bool("bride_previous_marriages")
        bride_church_switching    = _bool("bride_church_switching")
        bride_parents_religion    = _fg("bride_parents_religion")
        bride_church_society      = _fg("bride_church_society")

        # ── Bride medical ─────────────────────────────────────────────
        bride_blood_group           = _fg("bride_blood_group")
        bride_genotype              = _fg("bride_genotype")
        bride_psychological_status  = _fg("bride_psychological_status")
        bride_mental_illness_history= _fg("bride_mental_illness_history")
        bride_phobias               = _fg("bride_phobias")
        bride_allergies             = _fg("bride_allergies")

        # ── Extended groom personal ───────────────────────────────────
        groom_dob           = _date("groom_dob")
        groom_phone         = _fg("groom_phone")
        groom_social_media  = _fg("groom_social_media")
        groom_address       = _fg("groom_address")
        groom_parent_name   = _fg("groom_parent_name")
        groom_parent_address= _fg("groom_parent_address")
        groom_parents_alive = _fg("groom_parents_alive")
        groom_place_of_birth= _fg("groom_place_of_birth")
        groom_occupation    = _fg("groom_occupation")
        groom_education     = _fg("groom_education")
        groom_num_siblings  = _int("groom_num_siblings")
        groom_family_position= _fg("groom_family_position")

        # ── Groom religious ───────────────────────────────────────────
        groom_is_catholic         = _bool("groom_is_catholic")
        groom_domicile_parish     = _fg("groom_domicile_parish")
        groom_years_domicile      = _int("groom_years_domicile")
        groom_year_baptism        = _int("groom_year_baptism")
        groom_year_first_communion= _int("groom_year_first_communion")
        groom_year_confirmation   = _int("groom_year_confirmation")
        groom_previous_marriages  = _bool("groom_previous_marriages")
        groom_church_switching    = _bool("groom_church_switching")
        groom_parents_religion    = _fg("groom_parents_religion")
        groom_church_society      = _fg("groom_church_society")

        # ── Groom medical ─────────────────────────────────────────────
        groom_blood_group           = _fg("groom_blood_group")
        groom_genotype              = _fg("groom_genotype")
        groom_psychological_status  = _fg("groom_psychological_status")
        groom_mental_illness_history= _fg("groom_mental_illness_history")
        groom_phobias               = _fg("groom_phobias")
        groom_allergies             = _fg("groom_allergies")

        # ── Wedding & account ─────────────────────────────────────────
        wedding_date = _fg("wedding_date")

        required_fields = [
            bride_first, bride_last, bride_email,
            bride_phone, bride_address, bride_blood_group, bride_genotype,
            groom_first, groom_last, groom_email,
            groom_phone, groom_address, groom_blood_group, groom_genotype,
            password, confirm_password,
        ]
        if not all(required_fields):
            flash("Please complete all required registration fields.", "error")
            return redirect(url_for("register"))

        if not accepted_terms:
            flash("You must agree to the terms of service before registering.", "error")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return redirect(url_for("register"))

        if not EMAIL_PATTERN.match(bride_email) or not EMAIL_PATTERN.match(groom_email):
            flash("Please provide valid email addresses for both partners.", "error")
            return redirect(url_for("register"))

        if bride_email == groom_email:
            flash("Bride and groom email addresses must be different.", "error")
            return redirect(url_for("register"))

        if User.query.filter_by(email=bride_email).first():
            flash("An account with that email already exists. Please log in.", "error")
            return redirect(url_for("register"))

        user = User(
            email=bride_email,
            bride_first_name=bride_first,
            bride_last_name=bride_last,
            bride_email=bride_email,
            bride_parish=bride_parish,
            groom_first_name=groom_first,
            groom_last_name=groom_last,
            groom_email=groom_email,
            groom_parish=groom_parish,
            wedding_date=datetime.strptime(wedding_date, '%Y-%m-%d').date() if wedding_date else None,
            is_paid=False,
            is_admin=False,
            # Extended bride personal
            bride_dob=bride_dob,
            bride_phone=bride_phone,
            bride_social_media=bride_social_media or None,
            bride_address=bride_address or None,
            bride_parent_name=bride_parent_name or None,
            bride_parent_address=bride_parent_address or None,
            bride_parents_alive=bride_parents_alive or None,
            bride_place_of_birth=bride_place_of_birth or None,
            bride_occupation=bride_occupation or None,
            bride_education=bride_education or None,
            bride_num_siblings=bride_num_siblings,
            bride_family_position=bride_family_position or None,
            # Bride religious
            bride_is_catholic=bride_is_catholic,
            bride_domicile_parish=bride_domicile_parish or None,
            bride_years_domicile=bride_years_domicile,
            bride_year_baptism=bride_year_baptism,
            bride_year_first_communion=bride_year_first_communion,
            bride_year_confirmation=bride_year_confirmation,
            bride_previous_marriages=bride_previous_marriages,
            bride_church_switching=bride_church_switching,
            bride_parents_religion=bride_parents_religion or None,
            bride_church_society=bride_church_society or None,
            # Bride medical
            bride_blood_group=bride_blood_group or None,
            bride_genotype=bride_genotype or None,
            bride_psychological_status=bride_psychological_status or None,
            bride_mental_illness_history=bride_mental_illness_history or None,
            bride_phobias=bride_phobias or None,
            bride_allergies=bride_allergies or None,
            # Extended groom personal
            groom_dob=groom_dob,
            groom_phone=groom_phone,
            groom_social_media=groom_social_media or None,
            groom_address=groom_address or None,
            groom_parent_name=groom_parent_name or None,
            groom_parent_address=groom_parent_address or None,
            groom_parents_alive=groom_parents_alive or None,
            groom_place_of_birth=groom_place_of_birth or None,
            groom_occupation=groom_occupation or None,
            groom_education=groom_education or None,
            groom_num_siblings=groom_num_siblings,
            groom_family_position=groom_family_position or None,
            # Groom religious
            groom_is_catholic=groom_is_catholic,
            groom_domicile_parish=groom_domicile_parish or None,
            groom_years_domicile=groom_years_domicile,
            groom_year_baptism=groom_year_baptism,
            groom_year_first_communion=groom_year_first_communion,
            groom_year_confirmation=groom_year_confirmation,
            groom_previous_marriages=groom_previous_marriages,
            groom_church_switching=groom_church_switching,
            groom_parents_religion=groom_parents_religion or None,
            groom_church_society=groom_church_society or None,
            # Groom medical
            groom_blood_group=groom_blood_group or None,
            groom_genotype=groom_genotype or None,
            groom_psychological_status=groom_psychological_status or None,
            groom_mental_illness_history=groom_mental_illness_history or None,
            groom_phobias=groom_phobias or None,
            groom_allergies=groom_allergies or None,
        )
        user.set_password(password)
        user.ensure_registration_number()

        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("A couple account with that email already exists.", "error")
            return redirect(url_for("register"))

        session.clear()
        login_user(user)
        generate_csrf_token()
        session["last_activity"] = int(time.time())

        send_welcome_email(user)

        flash(f"Welcome, {user.get_couple_name()}! Your reference is {user.registration_number}. Please complete payment to unlock your dashboard.", "success")
        return redirect(url_for("payment"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
@rate_limit(limit=10, window_seconds=15 * 60, scope="auth")
@csrf_protect
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard") if current_user.is_paid else url_for("payment"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not EMAIL_PATTERN.match(email):
            flash("Please enter a valid email address.", "error")
            return redirect(url_for("login"))

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            session.clear()
            login_user(user, remember=False)
            generate_csrf_token()
            session["last_activity"] = int(time.time())

            if getattr(user, "force_password_change", False):
                flash("Please change your temporary password before continuing.", "warning")
                return redirect(url_for("change_password"))

            if user.is_admin:
                return redirect(url_for("admin_dashboard"))

            if user.is_paid:
                flash(f"Welcome back, {user.get_couple_name()}!", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Login successful! Please complete payment to access your dashboard.", "info")
                return redirect(url_for("payment"))
        else:
            flash("Invalid email or password. Please try again.", "error")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout", methods=["POST"], endpoint="user_logout")
@login_required
@csrf_protect
def user_logout():
    logout_user()
    session.clear()
    flash("You have been signed out safely.", "info")
    return redirect(url_for("landing"))


# ──────────────────────────────────────────────────
#  Clerk integration routes (scaffold)
# ──────────────────────────────────────────────────

@app.route("/clerk/sync", methods=["POST"])
@csrf_protect
def clerk_sync():
    """
    Called by Clerk JS after sign-in/sign-up.
    Verifies the Clerk session token and creates a Flask session.
    """
    if not app.config.get('CLERK_ENABLED'):
        return jsonify({"error": "Clerk not enabled"}), 400

    from clerk_auth import verify_clerk_session_token, sync_clerk_user_to_db
    token = request.form.get("session_token") or request.json.get("session_token", "")

    payload = verify_clerk_session_token(token)
    if not payload:
        return jsonify({"error": "Invalid session token"}), 401

    user = sync_clerk_user_to_db(payload, db, User)
    if not user:
        return jsonify({"error": "Could not create user"}), 500

    session.clear()
    login_user(user)
    generate_csrf_token()
    session["last_activity"] = int(time.time())

    redirect_url = url_for("dashboard") if user.is_paid else url_for("payment")
    return jsonify({"success": True, "redirect": redirect_url})


@app.route("/clerk/webhook", methods=["POST"])
def clerk_webhook():
    """
    Clerk webhook handler — syncs user events (created, deleted, updated).
    """
    if not app.config.get('CLERK_ENABLED'):
        return jsonify({"status": "disabled"}), 200

    from clerk_auth import verify_clerk_webhook, sync_clerk_user_to_db
    payload = request.get_data()
    svix_id = request.headers.get("svix-id", "")
    svix_timestamp = request.headers.get("svix-timestamp", "")
    svix_signature = request.headers.get("svix-signature", "")

    if not verify_clerk_webhook(payload, svix_id, svix_timestamp, svix_signature):
        return jsonify({"error": "Invalid signature"}), 400

    event = request.json
    event_type = event.get("type", "")
    data = event.get("data", {})

    if event_type == "user.created":
        sync_clerk_user_to_db(data, db, User)
    elif event_type == "user.deleted":
        clerk_user_id = data.get("id")
        if clerk_user_id:
            user = User.query.filter_by(clerk_user_id=clerk_user_id).first()
            if user:
                user.clerk_user_id = None  # Unlink rather than delete

    db.session.commit()
    return jsonify({"status": "ok"}), 200


# ──────────────────────────────────────────────────
#  User profile
# ──────────────────────────────────────────────────

@app.route("/profile", methods=["GET", "POST"])
@login_required
@csrf_protect
def profile():
    if request.method == "POST":
        # Handle photo upload
        if "profile_photo" in request.files:
            photo = request.files["profile_photo"]
            if photo and photo.filename and allowed_image(photo.filename):
                filename = f"couple_{current_user.id}_{secrets.token_hex(8)}.{photo.filename.rsplit('.', 1)[-1].lower()}"
                safe_name = secure_filename(filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
                photo.save(filepath)
                current_user.profile_photo_url = f"/static/uploads/{safe_name}"
                db.session.commit()
                flash("Profile photo updated successfully.", "success")
            elif photo and photo.filename:
                flash("Please upload a valid image file (PNG, JPG, JPEG, or WebP).", "error")

        return redirect(url_for("profile"))

    return render_template("profile.html", user=current_user)


# ──────────────────────────────────────────────────
#  Dashboard
# ──────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    if not current_user.is_paid:
        flash("Please complete payment to access your dashboard.", "warning")
        return redirect(url_for("payment"))

    return render_template(
        "dashboard.html",
        course_catalog=get_core_course_catalog(),
        doctrine_principles=get_doctrine_principles(),
        classroom_features=get_classroom_features(),
        live_sessions=get_live_classroom_schedule(),
        classroom_stream=get_classroom_stream(current_user),
        milestones=get_dashboard_milestones(current_user),
        session_timeout_minutes=SESSION_IDLE_TIMEOUT // 60,
    )


# ──────────────────────────────────────────────────
#  Payment
# ──────────────────────────────────────────────────

@app.route("/payment", methods=["GET", "POST"])
@login_required
@rate_limit(limit=20, window_seconds=30 * 60, scope="payment")
@csrf_protect
def payment():
    if current_user.is_paid:
        flash("You already have full access to your dashboard!", "info")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        idempotency_state = check_idempotency("payment")
        if idempotency_state == "duplicate":
            flash("That payment request was already received.", "info")
            return redirect(url_for("dashboard" if current_user.is_paid else "payment"))
        if idempotency_state == "invalid":
            flash("Your payment form expired. Please refresh and try again.", "error")
            return redirect(url_for("payment"))

        payment_method = request.form.get("payment_method")

        if payment_method == "paystack":
            paystack_key = app.config.get('PAYSTACK_SECRET_KEY')
            if paystack_key and not paystack_key.startswith('sk_test_xxxxx'):
                # Real Paystack: initialize transaction
                try:
                    import requests as req_lib
                    ref = generate_reference(current_user.id)
                    resp = req_lib.post(
                        "https://api.paystack.co/transaction/initialize",
                        headers={
                            "Authorization": f"Bearer {paystack_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "email": current_user.email,
                            "amount": app.config['COURSE_PRICE_KOBO'],
                            "reference": ref,
                            "callback_url": url_for("verify_payment", _external=True),
                            "metadata": {
                                "couple_name": current_user.get_couple_name(),
                                "registration_number": current_user.registration_number,
                            },
                        },
                        timeout=10,
                    )
                    data = resp.json()
                    if data.get("status") and data["data"].get("authorization_url"):
                        return redirect(data["data"]["authorization_url"])
                    else:
                        flash("Payment initialization failed. Please try again.", "error")
                        return redirect(url_for("payment"))
                except Exception as exc:
                    app.logger.error("Paystack init error: %s", exc)
                    flash("Payment service unavailable. Please try again shortly.", "error")
                    return redirect(url_for("payment"))
            else:
                # Dev mode: simulate successful payment
                try:
                    current_user.is_paid = True
                    db.session.commit()
                    send_payment_confirmation_email(current_user)
                except Exception:
                    db.session.rollback()
                    flash("Payment could not be recorded. Please try again.", "error")
                    return redirect(url_for("payment"))
                flash("Payment successful! Your dashboard is now unlocked.", "success")
                return redirect(url_for("dashboard"))

        flash("Please choose a valid payment method to continue.", "error")
        return redirect(url_for("payment"))

    return render_template(
        "payment.html",
        paystack_public_key=app.config.get('PAYSTACK_PUBLIC_KEY', ''),
    )


@app.route("/verify-payment")
@login_required
def verify_payment():
    reference = request.args.get('reference')
    if not reference:
        flash("Invalid payment reference.", "error")
        return redirect(url_for("payment"))

    paystack_key = app.config.get('PAYSTACK_SECRET_KEY')
    if paystack_key and not paystack_key.startswith('sk_test_xxxxx'):
        # Verify with real Paystack
        try:
            import requests as req_lib
            resp = req_lib.get(
                f"https://api.paystack.co/transaction/verify/{reference}",
                headers={"Authorization": f"Bearer {paystack_key}"},
                timeout=10,
            )
            data = resp.json()
            if (data.get("status") and
                    data["data"].get("status") == "success" and
                    data["data"].get("amount") >= app.config['COURSE_PRICE_KOBO']):
                current_user.is_paid = True
                db.session.commit()
                send_payment_confirmation_email(current_user)
                flash("Payment verified! Your dashboard is now unlocked.", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Payment verification failed. Please contact support.", "error")
                return redirect(url_for("payment"))
        except Exception as exc:
            app.logger.error("Paystack verify error: %s", exc)
            flash("Payment verification service unavailable. Please try again.", "error")
            return redirect(url_for("payment"))
    else:
        # Dev mode
        current_user.is_paid = True
        db.session.commit()
        flash("Payment verified! Your dashboard is now unlocked.", "success")
        return redirect(url_for("dashboard"))


# ──────────────────────────────────────────────────
#  Account management
# ──────────────────────────────────────────────────

@app.route("/change-password", methods=["GET", "POST"])
@login_required
@rate_limit(limit=10, window_seconds=30 * 60, scope="account")
@csrf_protect
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "error")
            return redirect(url_for("change_password"))

        if new_password != confirm_password:
            flash("New passwords do not match.", "error")
            return redirect(url_for("change_password"))

        if len(new_password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return redirect(url_for("change_password"))

        current_user.set_password(new_password)
        current_user.force_password_change = False
        db.session.commit()

        is_admin = current_user.is_admin
        logout_user()
        flash("Password changed successfully. Please log in with your new password.", "success")
        return redirect(url_for("login"))

    return render_template("change_password.html", user=current_user)


# ──────────────────────────────────────────────────
#  Admin routes
# ──────────────────────────────────────────────────

@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    total_users = User.query.count()
    paid_users = User.query.filter_by(is_paid=True).count()
    total_courses = Course.query.count()
    total_revenue = paid_users * 50000
    payment_rate = round((paid_users / total_users * 100) if total_users > 0 else 0, 1)

    start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0)
    new_users_this_month = User.query.filter(User.created_at >= start_of_month).count()
    unpaid_users = max(total_users - paid_users, 0)
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()

    revenue_labels, revenue_data, user_labels, user_growth_data = [], [], [], []
    for i in range(5, -1, -1):
        month = (datetime.now() - timedelta(days=30 * i)).strftime('%b')
        revenue_labels.append(month)
        user_labels.append(month)
        start_date = datetime.now() - timedelta(days=30 * (i + 1))
        end_date = datetime.now() - timedelta(days=30 * i)
        month_users = User.query.filter(User.created_at >= start_date, User.created_at < end_date).count()
        user_growth_data.append(month_users)
        month_paid = User.query.filter(User.is_paid == True, User.created_at >= start_date, User.created_at < end_date).count()
        revenue_data.append(month_paid * 50000)

    return render_template(
        "admin/admin_dashboard.html",
        total_users=total_users,
        paid_users=paid_users,
        unpaid_users=unpaid_users,
        total_revenue=f"{total_revenue:,}",
        total_courses=total_courses,
        active_courses=total_courses,
        payment_rate=payment_rate,
        new_users_this_month=new_users_this_month,
        recent_users=recent_users,
        revenue_labels=revenue_labels,
        revenue_data=revenue_data,
        user_labels=user_labels,
        user_growth_data=user_growth_data,
        active_page='dashboard',
    )


@app.route("/admin/users")
@login_required
@admin_required
def admin_users():
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'all')

    query = User.query.filter_by(is_admin=False)
    if search:
        query = query.filter(
            User.email.ilike(f'%{search}%') |
            User.bride_first_name.ilike(f'%{search}%') |
            User.groom_first_name.ilike(f'%{search}%') |
            User.registration_number.ilike(f'%{search}%')
        )
    if status_filter == 'paid':
        query = query.filter_by(is_paid=True)
    elif status_filter == 'unpaid':
        query = query.filter_by(is_paid=False)

    users = query.order_by(User.created_at.desc()).all()
    return render_template(
        "admin/admin_users.html",
        users=users,
        total_users=len(users),
        search=search,
        status_filter=status_filter,
        active_page='users',
    )


@app.route("/admin/courses")
@login_required
@admin_required
def admin_courses():
    courses = Course.query.all()
    return render_template(
        "admin/admin_courses.html",
        courses=courses,
        doctrine_tracks=get_core_course_catalog(),
        active_page='courses',
    )


@app.route("/admin/add-course", methods=["POST"])
@login_required
@admin_required
@csrf_protect
@rate_limit(limit=20, window_seconds=60 * 60, scope="admin")
def admin_add_course():
    idempotency_state = check_idempotency("admin_add_course")
    if idempotency_state == "duplicate":
        flash("That course submission was already received.", "info")
        return redirect(url_for("admin_courses"))
    if idempotency_state == "invalid":
        flash("The form expired. Please try again.", "error")
        return redirect(url_for("admin_courses"))

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    price = request.form.get("price")

    if not title:
        flash("Course title is required.", "error")
        return redirect(url_for("admin_courses"))

    if Course.query.filter(func.lower(Course.title) == title.lower()).first():
        flash("A course with that title already exists.", "error")
        return redirect(url_for("admin_courses"))

    new_course = Course(title=title, description=description, price=float(price) if price else 50000)
    try:
        db.session.add(new_course)
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("The course could not be created. Please try again.", "error")
        return redirect(url_for("admin_courses"))

    flash(f"Course '{title}' added successfully.", "success")
    return redirect(url_for("admin_courses"))


@app.route("/admin/delete-course/<int:course_id>", methods=["POST"])
@login_required
@admin_required
@csrf_protect
@rate_limit(limit=20, window_seconds=60 * 60, scope="admin")
def admin_delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    db.session.delete(course)
    db.session.commit()
    flash(f"Course '{course.title}' deleted.", "success")
    return redirect(url_for("admin_courses"))


@app.route("/admin/payments")
@login_required
@admin_required
def admin_payments():
    paid_users = User.query.filter_by(is_paid=True).order_by(User.created_at.desc()).all()
    total_revenue = len(paid_users) * 50000
    return render_template(
        "admin/admin_payments.html",
        payments=paid_users,
        total_revenue=f"{total_revenue:,}",
        total_paid=len(paid_users),
        total_unpaid=User.query.filter_by(is_paid=False).count(),
        active_page='payments',
    )


@app.route("/admin/analytics")
@login_required
@admin_required
def admin_analytics():
    daily_data = []
    for i in range(29, -1, -1):
        date_label = (datetime.now() - timedelta(days=i)).strftime('%b %d')
        day_start = (datetime.now() - timedelta(days=i)).replace(hour=0, minute=0, second=0)
        day_end = (datetime.now() - timedelta(days=i - 1)).replace(hour=0, minute=0, second=0) if i > 0 else datetime.now()
        count = User.query.filter(User.created_at >= day_start, User.created_at < day_end).count()
        daily_data.append({'date': date_label, 'count': count})

    total_30 = sum(d['count'] for d in daily_data)
    peak = max(daily_data, key=lambda d: d['count'], default={'date': '&#8212;', 'count': 0})
    max_c = max(peak['count'], 1)

    return render_template(
        "admin/admin_analytics.html",
        daily_data=daily_data,
        total_30=total_30,
        peak=peak,
        max_c=max_c,
        active_page='analytics',
    )


@app.route("/admin/toggle-payment/<int:user_id>", methods=["POST"])
@login_required
@admin_required
@csrf_protect
@rate_limit(limit=30, window_seconds=60 * 60, scope="admin")
def toggle_payment(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}
    user.is_paid = data.get('is_paid', False)
    db.session.commit()
    if user.is_paid:
        send_payment_confirmation_email(user)
    return jsonify({"success": True, "is_paid": user.is_paid})


@app.route("/admin/make-admin/<int:user_id>", methods=["POST"])
@login_required
@admin_required
@csrf_protect
@rate_limit(limit=10, window_seconds=60 * 60, scope="admin")
def make_admin(user_id):
    user = User.query.get_or_404(user_id)
    user.is_admin = True
    db.session.commit()
    flash(f"{user.email} is now an admin.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/manage-admins")
@login_required
@admin_required
def admin_manage_admins():
    admins = User.query.filter_by(is_admin=True).all()
    return render_template("admin/manage_admins.html", admins=admins, active_page='manage_admins')


@app.route("/admin/create-admin", methods=["POST"])
@login_required
@admin_required
@csrf_protect
@rate_limit(limit=10, window_seconds=60 * 60, scope="admin")
def admin_create_admin():
    email = request.form.get("email", "").strip().lower()
    name = request.form.get("name", "Admin User").strip()

    if not EMAIL_PATTERN.match(email):
        flash("Please enter a valid email address.", "error")
        return redirect(url_for("admin_manage_admins"))

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        existing_user.is_admin = True
        db.session.commit()
        flash(f"{email} has been granted admin access.", "success")
        return redirect(url_for("admin_manage_admins"))

    temp_password = secrets.token_urlsafe(10)
    name_parts = name.split()
    new_user = User(
        email=email,
        bride_first_name=name_parts[0] if name_parts else name,
        bride_last_name=name_parts[-1] if len(name_parts) > 1 else "",
        bride_email=email,
        groom_first_name=name_parts[0] if name_parts else name,
        groom_email=email,
        is_paid=True,
        is_admin=True,
        force_password_change=True,
    )
    new_user.set_password(temp_password)
    new_user.ensure_registration_number()
    db.session.add(new_user)
    db.session.commit()

    flash(f"Admin created. Email: {email} | Temp password: {temp_password}", "success")
    flash("The admin will be required to change their password on first login.", "warning")
    return redirect(url_for("admin_manage_admins"))


@app.route("/admin/reset-password/<int:user_id>", methods=["POST"])
@login_required
@admin_required
@csrf_protect
@rate_limit(limit=20, window_seconds=60 * 60, scope="admin")
def admin_reset_password(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Use the Change Password page to update your own password.", "error")
        return redirect(url_for("admin_manage_admins"))

    temp_password = secrets.token_urlsafe(10)
    user.set_password(temp_password)
    user.force_password_change = True
    db.session.commit()

    flash(f"Password reset for {user.email}. Temporary password: {temp_password}", "success")
    flash("The user will be required to change their password on next login.", "warning")
    return redirect(url_for("admin_manage_admins"))


@app.route("/admin/remove-admin/<int:user_id>", methods=["POST"])
@login_required
@admin_required
@csrf_protect
@rate_limit(limit=20, window_seconds=60 * 60, scope="admin")
def admin_remove_admin(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot remove your own admin privileges.", "error")
        return redirect(url_for("admin_manage_admins"))
    user.is_admin = False
    db.session.commit()
    flash(f"Admin privileges removed from {user.email}.", "success")
    return redirect(url_for("admin_manage_admins"))


# ──────────────────────────────────────────────────
#  Error handlers
# ──────────────────────────────────────────────────

@app.errorhandler(404)
def not_found_error(error):
    if request.path.startswith('/admin'):
        return render_template("admin/404.html"), 404
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    if request.path.startswith('/admin'):
        return render_template("admin/500.html"), 500
    return render_template("500.html"), 500


@app.errorhandler(403)
def forbidden_error(error):
    if request.path.startswith('/admin'):
        return render_template("admin/403.html"), 403
    return render_template("403.html"), 403


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_ENV") != "production",
    )
