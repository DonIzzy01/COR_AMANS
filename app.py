import os
import re
import secrets
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from threading import Lock

from flask import (Flask, abort, flash, redirect, render_template,
                   request, session, url_for, jsonify)
from dotenv import load_dotenv
from config import Config
from extensions import db, login_manager, mail
from models import User, Course, Resource, LiveSession, AuditLog
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from functools import lru_cache, wraps
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename
from circuit_breaker import CircuitBreaker
from observability import init_observability

load_dotenv()

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# ── Redis-backed rate limiter (falls back to in-memory if Redis is down) ──
REDIS_URL = os.environ.get('REDIS_URL', '')
_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if not REDIS_URL:
        return None
    try:
        import redis as redis_lib
        r = redis_lib.from_url(REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        r.ping()
        _redis_client = r
        logger.info('Redis connected: %s', REDIS_URL)
        return r
    except Exception as exc:
        logger.warning('Redis unavailable, using in-memory rate limiter: %s', exc)
        return None


# In-memory fallback (single-worker only)
RATE_LIMIT_STORE = defaultdict(list)
RATE_LIMIT_LOCK = Lock()

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SESSION_IDLE_TIMEOUT = 20 * 60

email_circuit = CircuitBreaker('email', failure_threshold=3, recovery_timeout=60)

# Initialize extensions
db.init_app(app)
mail.init_app(app)
login_manager.init_app(app)
init_observability(app)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.context_processor
def inject_globals():
    return {
        "csrf_token": generate_csrf_token,
        "idempotency_key": issue_idempotency_key,
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
            key = f"rl:{scope}:{request.endpoint}:{get_client_ip()}"
            r = _get_redis()
            if r:
                # Redis sliding window — works across all workers
                try:
                    pipe = r.pipeline()
                    pipe.zremrangebyscore(key, 0, now - window_seconds)
                    pipe.zcard(key)
                    pipe.zadd(key, {str(now): now})
                    pipe.expire(key, window_seconds + 1)
                    _, count, *_ = pipe.execute()
                    if count >= limit:
                        flash("Too many requests. Please wait a moment and try again.", "error")
                        response = redirect(request.referrer or url_for("landing"))
                        response.headers["Retry-After"] = str(window_seconds)
                        return response
                    return f(*args, **kwargs)
                except Exception:
                    pass  # Redis error → fall through to in-memory
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


def allowed_document(filename):
    return '.' in filename and filename.rsplit('.', 1)[-1].lower() == 'pdf'


def extract_video_info(url):
    """
    Parse a YouTube or Vimeo URL.
    Returns (embed_id, platform) or (None, None).
    """
    if not url:
        return None, None
    url = url.strip()
    # YouTube
    yt = re.search(
        r'(?:youtube\.com/(?:watch\?v=|embed/|live/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})',
        url
    )
    if yt:
        return yt.group(1), 'youtube'
    # Vimeo
    vm = re.search(r'vimeo\.com/(?:video/)?(\d+)', url)
    if vm:
        return vm.group(1), 'vimeo'
    return None, None


def write_audit(action, target_type=None, target_id=None, detail=None):
    """Record an admin/system action to the audit_logs table."""
    import json as _json
    user_id = current_user.id if current_user.is_authenticated else None
    log = AuditLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=_json.dumps(detail) if detail else None,
        ip_address=get_client_ip(),
    )
    db.session.add(log)
    # Committed by the calling route — no separate commit here.


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

    if app.config.get('FLASK_ENV') == 'production':
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"

    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' "
        "https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com "
        "https://fonts.googleapis.com; "
        "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob: https://img.youtube.com https://i.vimeocdn.com; "
        "connect-src 'self'; "
        "frame-src 'self' https://www.youtube.com https://player.vimeo.com "
        "https://youtube.com; "
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
            "title": "Marriage as Covenant and Sacrament",
            "duration": "2 hours",
            "format": "Doctrine seminar + mentor discussion",
            "summary": (
                "Marriage is not a mere social contract but a sacred covenant: "
                "'The matrimonial covenant, by which a man and a woman establish between themselves "
                "a partnership of the whole of life, is by its nature ordered toward the good of the spouses "
                "and the procreation and education of offspring' (CCC 1601). Among the baptized, "
                "Christ raised this covenant to the dignity of a sacrament."
            ),
            "highlights": [
                "Marriage originates in God's creative act, not human convention (CCC 1603)",
                "Christ's first miracle at Cana confirms the goodness of marriage (CCC 1613)",
                "Sacramental grace strengthens spouses for the duties of their state (CCC 1641–1642)",
            ],
            "refs": "CCC 1601, 1603, 1612–1617, 1638–1642, 1660–1661",
            "level": "Foundation",
        },
        {
            "slug": "consent-freedom-liturgy",
            "title": "Matrimonial Consent and Freedom",
            "duration": "1.5 hours",
            "format": "Guided workshop",
            "summary": (
                "'The Church holds the exchange of consent between the spouses to be the "
                "indispensable element that makes the marriage. If consent is lacking there is no marriage' "
                "(CCC 1626). This module examines what authentic consent requires: freedom from coercion, "
                "absence of canonical impediments, and personal capacity to enter a lifelong covenant."
            ),
            "highlights": [
                "Consent must be a free act of will — no human power can substitute for it (CCC 1628)",
                "Freedom from external constraint and internal impediment (CCC 1625)",
                "The priest receives consent as a witness on behalf of the Church (CCC 1630)",
            ],
            "refs": "CCC 1625–1637, 1662–1663",
            "level": "Core preparation",
        },
        {
            "slug": "unity-fidelity-indissolubility",
            "title": "Unity, Fidelity, and Indissolubility",
            "duration": "2 hours",
            "format": "Case-study classroom",
            "summary": (
                "'Love seeks to be definitive; it cannot be an arrangement until further notice' "
                "(CCC 1646). Christian marriage demands total self-gift. This module explores unity "
                "(one man and one woman, exclusively), fidelity (definitive and not provisional), "
                "and indissolubility (the bond that persists until death)."
            ),
            "highlights": [
                "The marriage bond is established by God and is perpetual and exclusive (CCC 1638)",
                "Unity is required by the equal personal dignity of husband and wife (CCC 1645)",
                "Fidelity mirrors God's own covenant faithfulness and Christ's fidelity (CCC 1647)",
            ],
            "refs": "CCC 1638, 1643–1651, 1664–1665",
            "level": "Formation",
        },
        {
            "slug": "domestic-church-prayer",
            "title": "The Domestic Church and Family Prayer",
            "duration": "1.5 hours",
            "format": "Prayer practicum + live session",
            "summary": (
                "The Second Vatican Council described the Christian family as the Ecclesia domestica "
                "— the domestic church. 'The Christian home is the place where children receive the first "
                "proclamation of the faith... a community of grace and prayer, a school of human virtues "
                "and of Christian charity' (CCC 1666)."
            ),
            "highlights": [
                "The family is 'Ecclesia domestica' — the domestic church (CCC 1656; LG 11)",
                "Parents are 'the first heralds of the faith' with regard to their children (CCC 1656)",
                "The Holy Family of Nazareth is the model for every Christian home",
            ],
            "refs": "CCC 1655–1658, 1666",
            "level": "Spiritual life",
        },
        {
            "slug": "openness-to-life",
            "title": "Openness to Life and Responsible Parenthood",
            "duration": "2 hours",
            "format": "Lecture + pastoral Q&A",
            "summary": (
                "'Children are really the supreme gift of marriage and contribute very substantially "
                "to the welfare of their parents' (CCC 1652). The Church teaches the intrinsic connection "
                "between the unitive and procreative meanings of the conjugal act, and presents natural "
                "family planning as a morally worthy approach to responsible parenthood."
            ),
            "highlights": [
                "Children are 'the supreme gift of marriage' (CCC 1652)",
                "Couples without children can radiate fruitfulness through charity and hospitality (CCC 1654)",
                "Polygamy, divorce, and refusal of fertility contradict the nature of marriage (CCC 1664)",
            ],
            "refs": "CCC 1652–1654, 1664; Humanae Vitae 16; Amoris Laetitia 80–82",
            "level": "Pastoral guidance",
        },
        {
            "slug": "communication-stewardship-mission",
            "title": "Christian Witness and Communication in Marriage",
            "duration": "1.5 hours",
            "format": "Applied classroom track",
            "summary": (
                "'Christ dwells with the couple and gives them the strength to carry crosses, rise after "
                "failings, and forgive one another' (CCC 1642). Drawing on Amoris Laetitia (2016), "
                "this module forms couples in the virtues that sustain marriage: patience, gratitude, "
                "generosity, and the ongoing willingness to seek and grant forgiveness."
            ),
            "highlights": [
                "Christ gives strength to bear hardship and calls couples to grow in communion (CCC 1644)",
                "Faithful marriage is itself a public witness to God's own fidelity (CCC 1648)",
                "Good Christian marriage requires generous, ongoing communication (Amoris Laetitia 218–222)",
            ],
            "refs": "CCC 1641–1642, 1644, 1648; Amoris Laetitia Ch. 4 & 6",
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
            "description": (
                "'The matrimonial covenant, by which a man and a woman establish between themselves "
                "a partnership of the whole of life, is by its nature ordered toward the good of the spouses "
                "and the procreation and education of offspring.' Among baptized persons, Christ raised "
                "this covenant to the dignity of a sacrament."
            ),
            "refs": "CCC 1601",
        },
        {
            "title": "The Indissoluble Bond",
            "description": (
                "'The marriage bond has been established by God himself in such a way that a marriage "
                "concluded and consummated between baptized persons can never be dissolved. This bond… "
                "gives rise to a covenant guaranteed by God's fidelity.'"
            ),
            "refs": "CCC 1640",
        },
        {
            "title": "Fidelity and Unity",
            "description": (
                "'Love seeks to be definitive; it cannot be an arrangement until further notice.' "
                "By its very nature conjugal love requires the inviolable fidelity of the spouses — "
                "the consequence of the total gift of themselves which they make to each other."
            ),
            "refs": "CCC 1646",
        },
        {
            "title": "The Domestic Church",
            "description": (
                "'The Christian home is the place where children receive the first proclamation of the faith. "
                "For this reason the family home is rightly called the domestic church — a community of grace "
                "and prayer, a school of human virtues and of Christian charity.'"
            ),
            "refs": "CCC 1666",
        },
        {
            "title": "Openness to Life",
            "description": (
                "'Children are really the supreme gift of marriage and contribute very substantially "
                "to the welfare of their parents.' Marriage and conjugal love are by nature ordered "
                "toward the procreation and education of children."
            ),
            "refs": "CCC 1652",
        },
        {
            "title": "Sacramental Grace",
            "description": (
                "'From a valid marriage arises a bond… furthermore, in a Christian marriage the spouses "
                "are strengthened and, as it were, consecrated for the duties and the dignity of their "
                "state by a special sacrament.'"
            ),
            "refs": "CCC 1638",
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

@app.route("/offline")
def offline_page():
    return render_template("offline.html"), 200


@app.route("/health")
def health_check():
    checks = {"status": "ok", "db": "ok", "redis": "ok"}
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        checks["db"] = "error"
        checks["status"] = "degraded"
    r = _get_redis()
    if r:
        try:
            r.ping()
        except Exception:
            checks["redis"] = "error"
    else:
        checks["redis"] = "unavailable"
    status_code = 200 if checks["status"] == "ok" else 503
    return jsonify(checks), status_code


# ── Settings ──────────────────────────────────────────────────────────────

@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html", prefs=current_user.get_preferences())


@app.route("/settings/theme", methods=["POST"])
@login_required
def settings_theme():
    data = request.get_json(silent=True) or {}
    theme = data.get("theme", "system")
    if theme not in ("light", "dark", "system"):
        return jsonify({"error": "invalid"}), 400
    current_user.set_preference("theme", theme)
    db.session.commit()
    return jsonify({"ok": True, "theme": theme})


@app.route("/settings/pref", methods=["POST"])
@login_required
def settings_pref():
    data = request.get_json(silent=True) or {}
    key   = data.get("key")
    value = data.get("value")
    allowed = {"theme", "compact_mode", "email_notifications"}
    if key not in allowed:
        return jsonify({"error": "unknown key"}), 400
    current_user.set_preference(key, value)
    db.session.commit()
    return jsonify({"ok": True})


# ── Search ────────────────────────────────────────────────────────────────

@app.route("/search")
@login_required
def search():
    q = request.args.get("q", "").strip()
    results = {"resources": [], "sessions": []}
    if len(q) >= 2:
        like = f"%{q}%"
        results["resources"] = Resource.query.filter(
            Resource.is_published.is_(True),
            or_(Resource.title.ilike(like), Resource.description.ilike(like),
                Resource.tags.ilike(like))
        ).order_by(Resource.sort_order).limit(20).all()
        results["sessions"] = LiveSession.query.filter(
            or_(LiveSession.title.ilike(like), LiveSession.description.ilike(like),
                LiveSession.host_name.ilike(like))
        ).order_by(LiveSession.scheduled_at.desc()).limit(10).all()
    return render_template("search.html", q=q, results=results)


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
        reg_num = request.form.get("registration_number", "").strip().upper()
        password = request.form.get("password", "")

        if not reg_num:
            flash("Please enter your registration number.", "error")
            return redirect(url_for("login"))

        user = User.query.filter_by(registration_number=reg_num).first()

        if user and user.is_locked():
            remaining = int((user.locked_until - datetime.utcnow()).total_seconds() // 60) + 1
            flash(f"Too many failed attempts. Account locked for {remaining} more minute(s).", "error")
            return redirect(url_for("login"))

        if user and user.check_password(password):
            user.failed_login_attempts = 0
            user.locked_until = None
            db.session.commit()

            session.clear()
            login_user(user, remember=False)
            generate_csrf_token()
            session["last_activity"] = int(time.time())

            if getattr(user, "force_password_change", False):
                flash("Please change your temporary password before continuing.", "warning")
                return redirect(url_for("change_password"))

            if user.is_paid:
                flash(f"Welcome back, {user.get_couple_name()}!", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Login successful! Please complete payment to access your dashboard.", "info")
                return redirect(url_for("payment"))
        else:
            if user:
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                if user.failed_login_attempts >= 5:
                    user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                    db.session.commit()
                    flash("Too many failed attempts. Account locked for 15 minutes.", "error")
                else:
                    db.session.commit()
                    remaining = 5 - user.failed_login_attempts
                    flash(f"Invalid credentials. {remaining} attempt(s) remaining.", "error")
            else:
                flash("Invalid registration number or password.", "error")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/admin/login", methods=["GET", "POST"])
@rate_limit(limit=10, window_seconds=15 * 60, scope="admin_auth")
@csrf_protect
def admin_login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("dashboard") if current_user.is_paid else url_for("payment"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not EMAIL_PATTERN.match(email):
            flash("Please enter a valid email address.", "error")
            return redirect(url_for("admin_login"))

        user = User.query.filter_by(email=email, is_admin=True).first()

        if user and user.is_locked():
            remaining = int((user.locked_until - datetime.utcnow()).total_seconds() // 60) + 1
            flash(f"Account is locked. Try again in {remaining} minute(s).", "error")
            return redirect(url_for("admin_login"))

        if user and user.check_password(password):
            user.failed_login_attempts = 0
            user.locked_until = None
            db.session.commit()

            session.clear()
            login_user(user, remember=False)
            generate_csrf_token()
            session["last_activity"] = int(time.time())
            write_audit('admin.login', 'user', user.id)
            db.session.commit()

            if user.force_password_change:
                flash("Please change your temporary password before continuing.", "warning")
                return redirect(url_for("change_password"))

            flash(f"Welcome back, {user.email}.", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            if user:
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                if user.failed_login_attempts >= 5:
                    user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                    db.session.commit()
                    flash("Too many failed attempts. Account locked for 15 minutes.", "error")
                else:
                    db.session.commit()
            flash("Invalid credentials.", "error")
            return redirect(url_for("admin_login"))

    return render_template("admin/admin_login.html")


@app.route("/logout", methods=["POST"], endpoint="user_logout")
@login_required
@csrf_protect
def user_logout():
    logout_user()
    session.clear()
    flash("You have been signed out safely.", "info")
    return redirect(url_for("landing"))


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

    # Live sessions: upcoming first, then most recent
    upcoming_sessions = (LiveSession.query
        .filter(LiveSession.status.in_(['upcoming', 'live']))
        .order_by(LiveSession.scheduled_at.asc())
        .limit(3).all())

    # Featured resources (pinned + newest)
    featured_resources = (Resource.query
        .filter_by(is_published=True)
        .order_by(Resource.is_featured.desc(), Resource.created_at.desc())
        .limit(6).all())

    # Recent recordings
    recent_recordings = (LiveSession.query
        .filter(LiveSession.status == 'completed', LiveSession.recording_embed_id.isnot(None))
        .order_by(LiveSession.scheduled_at.desc())
        .limit(3).all())

    return render_template(
        "dashboard.html",
        course_catalog=get_core_course_catalog(),
        doctrine_principles=get_doctrine_principles(),
        live_sessions=upcoming_sessions,
        featured_resources=featured_resources,
        recent_recordings=recent_recordings,
        milestones=get_dashboard_milestones(current_user),
        session_timeout_minutes=SESSION_IDLE_TIMEOUT // 60,
        overall_progress=current_user.overall_progress(),
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
        month_paid = User.query.filter(User.is_paid.is_(True), User.created_at >= start_date, User.created_at < end_date).count()
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
#  Resource library (couples)
# ──────────────────────────────────────────────────

@app.route("/resources")
@login_required
def resources():
    if not current_user.is_paid:
        flash("Please complete payment to access formation resources.", "warning")
        return redirect(url_for("payment"))

    category = request.args.get('category', 'all')
    module = request.args.get('module', 'all')
    rtype = request.args.get('type', 'all')

    q = Resource.query.filter_by(is_published=True)
    if category != 'all':
        q = q.filter_by(category=category)
    if module != 'all':
        q = q.filter_by(module_slug=module)
    if rtype != 'all':
        q = q.filter_by(resource_type=rtype)

    all_resources = q.order_by(Resource.is_featured.desc(), Resource.sort_order.asc(), Resource.created_at.desc()).all()
    return render_template(
        "resources.html",
        resources=all_resources,
        course_catalog=get_core_course_catalog(),
        active_category=category,
        active_module=module,
        active_type=rtype,
    )


@app.route("/resources/<int:resource_id>")
@login_required
def resource_detail(resource_id):
    if not current_user.is_paid:
        return redirect(url_for("payment"))
    resource = Resource.query.filter_by(id=resource_id, is_published=True).first_or_404()
    return render_template("resource_detail.html", resource=resource)


# ──────────────────────────────────────────────────
#  Live sessions (couples)
# ──────────────────────────────────────────────────

@app.route("/sessions")
@login_required
def sessions():
    if not current_user.is_paid:
        flash("Please complete payment to access live sessions.", "warning")
        return redirect(url_for("payment"))

    upcoming = (LiveSession.query
        .filter(LiveSession.status.in_(['upcoming', 'live']))
        .order_by(LiveSession.scheduled_at.asc()).all())
    past = (LiveSession.query
        .filter(LiveSession.status == 'completed')
        .order_by(LiveSession.scheduled_at.desc()).limit(20).all())
    return render_template("sessions.html", upcoming=upcoming, past=past)


@app.route("/sessions/<int:session_id>")
@login_required
def session_detail(session_id):
    if not current_user.is_paid:
        return redirect(url_for("payment"))
    ls = LiveSession.query.get_or_404(session_id)
    return render_template("session_detail.html", ls=ls)


# ──────────────────────────────────────────────────
#  Admin: resources
# ──────────────────────────────────────────────────

DOCS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', 'documents')
os.makedirs(DOCS_FOLDER, exist_ok=True)


@app.route("/admin/resources")
@login_required
@admin_required
def admin_resources():
    resources = Resource.query.order_by(Resource.created_at.desc()).all()
    return render_template(
        "admin/admin_resources.html",
        resources=resources,
        course_catalog=get_core_course_catalog(),
        active_page='resources',
    )


@app.route("/admin/resources/add", methods=["GET", "POST"])
@login_required
@admin_required
@csrf_protect
@rate_limit(limit=30, window_seconds=60 * 60, scope="admin")
def admin_add_resource():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        resource_type = request.form.get("resource_type", "video")
        module_slug = request.form.get("module_slug", "").strip()
        category = request.form.get("category", "general")
        tags = request.form.get("tags", "").strip()
        is_featured = request.form.get("is_featured") == "1"
        sort_order = int(request.form.get("sort_order", 0) or 0)
        video_duration = request.form.get("video_duration", "").strip()

        if not title:
            flash("Title is required.", "error")
            return redirect(url_for("admin_add_resource"))

        new_res = Resource(
            title=title,
            description=description or None,
            resource_type=resource_type,
            module_slug=module_slug or None,
            category=category,
            tags=tags or None,
            is_featured=is_featured,
            sort_order=sort_order,
            uploaded_by=current_user.id,
        )

        if resource_type == "video":
            video_url = request.form.get("video_url", "").strip()
            embed_id, platform = extract_video_info(video_url)
            if not embed_id:
                flash("Could not parse a YouTube or Vimeo ID from that URL.", "error")
                return redirect(url_for("admin_add_resource"))
            new_res.video_url = video_url
            new_res.video_embed_id = embed_id
            new_res.video_platform = platform
            new_res.video_duration = video_duration or None

        elif resource_type == "document":
            file = request.files.get("document_file")
            if not file or not file.filename:
                flash("Please select a PDF file to upload.", "error")
                return redirect(url_for("admin_add_resource"))
            if not allowed_document(file.filename):
                flash("Only PDF files are accepted.", "error")
                return redirect(url_for("admin_add_resource"))
            safe_name = f"doc_{secrets.token_hex(10)}_{secure_filename(file.filename)}"
            file_path = os.path.join(DOCS_FOLDER, safe_name)
            file.save(file_path)
            file_size_kb = max(1, os.path.getsize(file_path) // 1024)
            new_res.file_path = f"documents/{safe_name}"
            new_res.file_name = file.filename
            new_res.file_size_kb = file_size_kb

        try:
            db.session.add(new_res)
            write_audit('resource.create', 'resource', detail={'title': title, 'type': resource_type})
            db.session.commit()
            flash(f"Resource '{title}' added successfully.", "success")
        except Exception:
            db.session.rollback()
            flash("Could not save resource. Please try again.", "error")

        return redirect(url_for("admin_resources"))

    return render_template(
        "admin/admin_resource_form.html",
        resource=None,
        course_catalog=get_core_course_catalog(),
        active_page='resources',
    )


@app.route("/admin/resources/<int:resource_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
@csrf_protect
def admin_edit_resource(resource_id):
    res = Resource.query.get_or_404(resource_id)

    if request.method == "POST":
        res.title = request.form.get("title", "").strip() or res.title
        res.description = request.form.get("description", "").strip() or None
        res.module_slug = request.form.get("module_slug", "").strip() or None
        res.category = request.form.get("category", res.category)
        res.tags = request.form.get("tags", "").strip() or None
        res.is_featured = request.form.get("is_featured") == "1"
        res.sort_order = int(request.form.get("sort_order", 0) or 0)
        res.is_published = request.form.get("is_published") == "1"
        res.video_duration = request.form.get("video_duration", "").strip() or res.video_duration

        if res.resource_type == "video":
            new_url = request.form.get("video_url", "").strip()
            if new_url and new_url != res.video_url:
                embed_id, platform = extract_video_info(new_url)
                if embed_id:
                    res.video_url = new_url
                    res.video_embed_id = embed_id
                    res.video_platform = platform
                else:
                    flash("Could not parse video URL — keeping previous URL.", "warning")

        res.updated_at = datetime.utcnow()
        try:
            write_audit('resource.edit', 'resource', resource_id, {'title': res.title})
            db.session.commit()
            flash("Resource updated.", "success")
        except Exception:
            db.session.rollback()
            flash("Update failed. Please try again.", "error")

        return redirect(url_for("admin_resources"))

    return render_template(
        "admin/admin_resource_form.html",
        resource=res,
        course_catalog=get_core_course_catalog(),
        active_page='resources',
    )


@app.route("/admin/resources/<int:resource_id>/delete", methods=["POST"])
@login_required
@admin_required
@csrf_protect
def admin_delete_resource(resource_id):
    res = Resource.query.get_or_404(resource_id)
    title = res.title
    if res.file_path:
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], res.file_path)
        if os.path.exists(full_path):
            os.remove(full_path)
    try:
        write_audit('resource.delete', 'resource', resource_id, {'title': title})
        db.session.delete(res)
        db.session.commit()
        flash(f"Resource '{title}' deleted.", "success")
    except Exception:
        db.session.rollback()
        flash("Delete failed.", "error")
    return redirect(url_for("admin_resources"))


@app.route("/admin/resources/<int:resource_id>/toggle-published", methods=["POST"])
@login_required
@admin_required
@csrf_protect
def admin_toggle_resource_published(resource_id):
    res = Resource.query.get_or_404(resource_id)
    res.is_published = not res.is_published
    db.session.commit()
    return jsonify({"success": True, "is_published": res.is_published})


# ──────────────────────────────────────────────────
#  Admin: live sessions
# ──────────────────────────────────────────────────

@app.route("/admin/sessions")
@login_required
@admin_required
def admin_sessions():
    sessions = LiveSession.query.order_by(LiveSession.scheduled_at.desc()).all()
    return render_template(
        "admin/admin_sessions.html",
        sessions=sessions,
        course_catalog=get_core_course_catalog(),
        active_page='sessions',
    )


@app.route("/admin/sessions/add", methods=["GET", "POST"])
@login_required
@admin_required
@csrf_protect
@rate_limit(limit=20, window_seconds=60 * 60, scope="admin")
def admin_add_session():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        host_name = request.form.get("host_name", "").strip()
        host_role = request.form.get("host_role", "").strip()
        scheduled_at_str = request.form.get("scheduled_at", "")
        duration = int(request.form.get("duration_minutes", 60) or 60)
        meeting_url = request.form.get("meeting_url", "").strip()
        meeting_id = request.form.get("meeting_id", "").strip()
        meeting_password = request.form.get("meeting_password", "").strip()
        platform = request.form.get("platform", "zoom")
        module_slug = request.form.get("module_slug", "").strip()
        session_topic = request.form.get("session_topic", "").strip()

        if not title or not scheduled_at_str:
            flash("Title and scheduled date/time are required.", "error")
            return redirect(url_for("admin_add_session"))

        try:
            scheduled_at = datetime.strptime(scheduled_at_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash("Invalid date/time format.", "error")
            return redirect(url_for("admin_add_session"))

        ls = LiveSession(
            title=title,
            description=description or None,
            host_name=host_name or None,
            host_role=host_role or None,
            scheduled_at=scheduled_at,
            duration_minutes=duration,
            meeting_url=meeting_url or None,
            meeting_id=meeting_id or None,
            meeting_password=meeting_password or None,
            platform=platform,
            module_slug=module_slug or None,
            session_topic=session_topic or None,
            status='upcoming',
            created_by=current_user.id,
        )
        try:
            db.session.add(ls)
            write_audit('session.create', 'session', detail={'title': title})
            db.session.commit()
            flash(f"Session '{title}' scheduled.", "success")
        except Exception:
            db.session.rollback()
            flash("Could not save session.", "error")
        return redirect(url_for("admin_sessions"))

    return render_template(
        "admin/admin_session_form.html",
        ls=None,
        course_catalog=get_core_course_catalog(),
        active_page='sessions',
    )


@app.route("/admin/sessions/<int:session_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
@csrf_protect
def admin_edit_session(session_id):
    ls = LiveSession.query.get_or_404(session_id)

    if request.method == "POST":
        ls.title = request.form.get("title", "").strip() or ls.title
        ls.description = request.form.get("description", "").strip() or None
        ls.host_name = request.form.get("host_name", "").strip() or None
        ls.host_role = request.form.get("host_role", "").strip() or None
        ls.duration_minutes = int(request.form.get("duration_minutes", 60) or 60)
        ls.meeting_url = request.form.get("meeting_url", "").strip() or None
        ls.meeting_id = request.form.get("meeting_id", "").strip() or None
        ls.meeting_password = request.form.get("meeting_password", "").strip() or None
        ls.platform = request.form.get("platform", ls.platform)
        ls.module_slug = request.form.get("module_slug", "").strip() or None
        ls.session_topic = request.form.get("session_topic", "").strip() or None
        ls.status = request.form.get("status", ls.status)

        # Recording URL
        rec_url = request.form.get("recording_url", "").strip()
        if rec_url:
            embed_id, platform = extract_video_info(rec_url)
            ls.recording_url = rec_url
            ls.recording_embed_id = embed_id
            ls.recording_platform = platform

        scheduled_at_str = request.form.get("scheduled_at", "")
        if scheduled_at_str:
            try:
                ls.scheduled_at = datetime.strptime(scheduled_at_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash("Invalid date/time format — keeping original time.", "warning")

        ls.updated_at = datetime.utcnow()
        try:
            write_audit('session.edit', 'session', session_id, {'title': ls.title})
            db.session.commit()
            flash("Session updated.", "success")
        except Exception:
            db.session.rollback()
            flash("Update failed.", "error")
        return redirect(url_for("admin_sessions"))

    return render_template(
        "admin/admin_session_form.html",
        ls=ls,
        course_catalog=get_core_course_catalog(),
        active_page='sessions',
    )


@app.route("/admin/sessions/<int:session_id>/delete", methods=["POST"])
@login_required
@admin_required
@csrf_protect
def admin_delete_session(session_id):
    ls = LiveSession.query.get_or_404(session_id)
    title = ls.title
    try:
        write_audit('session.delete', 'session', session_id, {'title': title})
        db.session.delete(ls)
        db.session.commit()
        flash(f"Session '{title}' deleted.", "success")
    except Exception:
        db.session.rollback()
        flash("Delete failed.", "error")
    return redirect(url_for("admin_sessions"))


@app.route("/admin/sessions/<int:session_id>/cancel", methods=["POST"])
@login_required
@admin_required
@csrf_protect
def admin_cancel_session(session_id):
    ls = LiveSession.query.get_or_404(session_id)
    ls.status = 'cancelled'
    write_audit('session.cancel', 'session', session_id, {'title': ls.title})
    db.session.commit()
    return jsonify({"success": True})


# ──────────────────────────────────────────────────
#  Admin: audit log
# ──────────────────────────────────────────────────

@app.route("/admin/audit")
@login_required
@admin_required
def admin_audit():
    logs = (AuditLog.query
        .order_by(AuditLog.created_at.desc())
        .limit(200).all())
    return render_template("admin/admin_audit.html", logs=logs, active_page='audit')


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
