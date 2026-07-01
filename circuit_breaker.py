"""
Simple thread-safe circuit breaker.

Usage:
    email_cb = CircuitBreaker('email', failure_threshold=3, recovery_timeout=60)

    @email_cb
    def send_mail(...): ...
"""
import time
import logging
from threading import Lock
from functools import wraps

logger = logging.getLogger(__name__)

_CLOSED  = 'closed'    # normal operation
_OPEN    = 'open'      # tripped — calls fail fast
_HALF    = 'half-open' # one probe call to test recovery


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5,
                 recovery_timeout: int = 30, expected_exception: type = Exception):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout  = recovery_timeout
        self.expected_exception = expected_exception

        self._state      = _CLOSED
        self._failures   = 0
        self._opened_at  = None
        self._lock       = Lock()

    @property
    def state(self):
        with self._lock:
            if self._state == _OPEN:
                if time.monotonic() - self._opened_at >= self.recovery_timeout:
                    self._state = _HALF
                    logger.info('CircuitBreaker[%s] → half-open', self.name)
            return self._state

    def _success(self):
        with self._lock:
            self._failures = 0
            if self._state != _CLOSED:
                logger.info('CircuitBreaker[%s] → closed', self.name)
            self._state = _CLOSED

    def _failure(self):
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._state     = _OPEN
                self._opened_at = time.monotonic()
                logger.warning('CircuitBreaker[%s] → open (%d failures)',
                               self.name, self._failures)

    def __call__(self, fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if self.state == _OPEN:
                raise RuntimeError(f'CircuitBreaker[{self.name}] is open — call blocked')
            try:
                result = fn(*args, **kwargs)
                self._success()
                return result
            except self.expected_exception as exc:
                self._failure()
                raise exc
        return wrapper

    def call(self, fn, *args, **kwargs):
        """Alternative: cb.call(func, arg1, arg2)"""
        return self.__call__(fn)(*args, **kwargs)
