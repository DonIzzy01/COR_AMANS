import os
import pytest

# Must be set before importing app so Config reads them at module load time
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
os.environ.setdefault('SECRET_KEY', 'ci-test-secret-key-not-for-production')
os.environ.setdefault('FLASK_ENV', 'testing')

from app import app as _app          # noqa: E402
from extensions import db as _db     # noqa: E402


@pytest.fixture(scope='session')
def app():
    _app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'MAIL_SUPPRESS_SEND': True,
    })
    with _app.app_context():
        _db.create_all()
        yield _app
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
