"""
Celery background tasks.

Worker start:  celery -A tasks worker --loglevel=info --concurrency=2
Beat scheduler: celery -A tasks beat  --loglevel=info
"""
import os
import logging
from celery import Celery
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')

celery_app = Celery(
    'cor_amans',
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='Africa/Lagos',
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,           # re-queue on worker crash
    worker_prefetch_multiplier=1,  # fair dispatch across workers
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)


# ── Email tasks ──────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, to: str, subject: str, body_html: str, body_text: str = ''):
    """Send an email. Retries 3× with 60s delay on failure."""
    try:
        from app import app, mail
        from flask_mail import Message
        with app.app_context():
            msg = Message(subject=subject, recipients=[to],
                          html=body_html, body=body_text or subject)
            mail.send(msg)
            logger.info('Email sent to %s: %s', to, subject)
    except Exception as exc:
        logger.warning('Email failed (attempt %d): %s', self.request.retries + 1, exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def send_payment_confirmation_task(self, user_id: int):
    """Send payment confirmation email for a user."""
    try:
        from app import app
        from models import User
        with app.app_context():
            user = User.query.get(user_id)
            if not user:
                return
            subject = 'Payment Confirmed — COR AMANS'
            body = f"""
<h2>Payment Confirmed</h2>
<p>Dear {user.get_couple_name()},</p>
<p>Your payment has been confirmed. You now have full access to the COR AMANS
formation programme.</p>
<p>Your registration number is: <strong>{user.registration_number}</strong></p>
<p>Log in to your dashboard to begin your formation journey.</p>
<br><p>With prayers,<br>The COR AMANS Team</p>
"""
            send_email_task.delay(user.email, subject, body)
            logger.info('Payment confirmation queued for user %d', user_id)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def send_session_reminder_task(self, session_id: int):
    """Send a live session reminder 15 minutes before it starts."""
    try:
        from app import app
        from models import LiveSession, User
        with app.app_context():
            ls = LiveSession.query.get(session_id)
            if not ls:
                return
            couples = User.query.filter_by(is_paid=True, is_admin=False).all()
            for couple in couples:
                prefs = couple.get_preferences()
                if not prefs.get('email_notifications', True):
                    continue
                subject = f'Live Session Starting Soon — {ls.title}'
                body = f"""
<h2>{ls.title}</h2>
<p>Your live formation session starts in 15 minutes.</p>
<p><strong>Host:</strong> {ls.host_name}<br>
<strong>Platform:</strong> {ls.platform}<br>
<strong>Join link:</strong> <a href="{ls.meeting_url}">{ls.meeting_url}</a></p>
"""
                send_email_task.delay(couple.email, subject, body)
            logger.info('Session reminders queued for session %d', session_id)
    except Exception as exc:
        raise self.retry(exc=exc)


# ── Scheduled tasks ──────────────────────────────────────────

@celery_app.task
def cleanup_expired_sessions():
    """Remove expired audit log entries older than 90 days."""
    try:
        from app import app, db
        from models import AuditLog
        from datetime import datetime, timedelta
        with app.app_context():
            cutoff = datetime.utcnow() - timedelta(days=90)
            deleted = AuditLog.query.filter(AuditLog.created_at < cutoff).delete()
            db.session.commit()
            logger.info('Cleaned up %d old audit log entries', deleted)
    except Exception as exc:
        logger.error('Audit cleanup failed: %s', exc)


celery_app.conf.beat_schedule = {
    'cleanup-audit-logs-weekly': {
        'task': 'tasks.cleanup_expired_sessions',
        'schedule': 604800,  # once a week
    },
}
