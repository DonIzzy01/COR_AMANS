"""
Observability — structured JSON logging, request tracing, metrics.

Call init_observability(app) once in app startup.
"""
import os
import uuid
import time
import logging
import json
from datetime import datetime
from flask import request, g


class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON for log aggregators (Loki, CloudWatch, etc.)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            'ts':      datetime.utcnow().isoformat() + 'Z',
            'level':   record.levelname,
            'logger':  record.name,
            'msg':     record.getMessage(),
        }
        if record.exc_info:
            payload['exc'] = self.formatException(record.exc_info)
        # Attach request context when available
        try:
            payload['request_id'] = getattr(g, 'request_id', None)
            payload['method']     = request.method
            payload['path']       = request.path
        except RuntimeError:
            pass
        if record.levelno >= logging.ERROR and record.exc_info:
            payload['traceback'] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def init_observability(app):
    """Wire up JSON logging and per-request tracing."""

    # Only switch to JSON in production; keep readable logs in dev
    if os.environ.get('FLASK_ENV') == 'production':
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logging.root.handlers = [handler]
        logging.root.setLevel(logging.INFO)
        app.logger.handlers = []

    @app.before_request
    def _start_timer():
        g.request_id  = request.headers.get('X-Request-ID') or uuid.uuid4().hex[:12]
        g.request_start = time.monotonic()

    @app.after_request
    def _log_request(response):
        duration_ms = round((time.monotonic() - g.get('request_start', time.monotonic())) * 1000, 1)
        # Skip noisy health-check logs
        if request.path == '/health':
            return response
        app.logger.info(
            '%s %s %d %.1fms',
            request.method, request.path, response.status_code, duration_ms,
            extra={
                'request_id': g.get('request_id'),
                'ip': request.remote_addr,
                'duration_ms': duration_ms,
                'status': response.status_code,
            }
        )
        response.headers['X-Request-ID'] = g.get('request_id', '')
        return response

    app.logger.info('Observability initialised (env=%s)', os.environ.get('FLASK_ENV', 'development'))


def get_request_id() -> str:
    try:
        return g.get('request_id', '')
    except RuntimeError:
        return ''
