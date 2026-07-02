import logging

# ── Workers ───────────────────────────────────────────────────────────────────
bind    = "0.0.0.0:5000"
workers = 2
timeout = 120

# ── Logging ───────────────────────────────────────────────────────────────────
accesslog  = "-"   # stdout
errorlog   = "-"   # stderr
loglevel   = "info"

# Filter /health and /favicon.ico out of the access log so Docker's
# 30-second health checks don't drown out real traffic.
class _SilentPaths(logging.Filter):
    _SKIP = ("/health", "/favicon.ico")

    def filter(self, record):
        msg = record.getMessage()
        return not any(p in msg for p in self._SKIP)


logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "silent_paths": {"()": _SilentPaths}
    },
    "handlers": {
        "console": {
            "class":   "logging.StreamHandler",
            "stream":  "ext://sys.stdout",
            "filters": ["silent_paths"],
        },
        "error_console": {
            "class":  "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "gunicorn.access": {
            "handlers":  ["console"],
            "level":     "INFO",
            "propagate": False,
        },
        "gunicorn.error": {
            "handlers":  ["error_console"],
            "level":     "INFO",
            "propagate": False,
        },
    },
}
