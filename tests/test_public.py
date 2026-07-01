"""
Tests for public-facing routes that don't require authentication.
All tests use an in-memory SQLite database (see conftest.py).
"""


def test_health_endpoint(client):
    r = client.get('/health')
    assert r.status_code == 200
    data = r.get_json()
    assert data['status'] in ('ok', 'degraded')
    assert 'db' in data
    assert 'redis' in data


def test_health_db_key_present(client):
    r = client.get('/health')
    data = r.get_json()
    assert data['db'] in ('ok', 'error')


def test_landing_page(client):
    r = client.get('/')
    assert r.status_code == 200


def test_login_page_loads(client):
    r = client.get('/login')
    assert r.status_code == 200
    assert b'login' in r.data.lower() or b'sign in' in r.data.lower()


def test_register_page_loads(client):
    r = client.get('/register')
    assert r.status_code == 200


def test_courses_page_loads(client):
    r = client.get('/courses')
    assert r.status_code == 200


def test_about_page_loads(client):
    r = client.get('/about')
    assert r.status_code == 200


def test_offline_page_loads(client):
    r = client.get('/offline')
    assert r.status_code == 200


def test_dashboard_redirects_anonymous(client):
    r = client.get('/dashboard')
    assert r.status_code in (302, 401)
    if r.status_code == 302:
        assert '/login' in r.headers['Location']


def test_admin_dashboard_redirects_anonymous(client):
    r = client.get('/admin')
    assert r.status_code in (302, 401)


def test_profile_redirects_anonymous(client):
    r = client.get('/profile')
    assert r.status_code in (302, 401)


def test_settings_redirects_anonymous(client):
    r = client.get('/settings')
    assert r.status_code in (302, 401)


def test_invalid_route_returns_404(client):
    r = client.get('/this-page-does-not-exist-xyz')
    assert r.status_code == 404


def test_csrf_token_in_login_form(client):
    r = client.get('/login')
    assert b'csrf_token' in r.data


def test_admin_login_page_loads(client):
    r = client.get('/admin/login')
    assert r.status_code == 200
