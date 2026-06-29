"""
COR AMANS Load Test — run with:
    pip install locust
    locust -f locustfile.py --host http://localhost:5001

Then open http://localhost:8089 to start a test.
"""

import re
from locust import HttpUser, task, between


def _csrf(response_text):
    m = re.search(r'name="csrf_token" value="([^"]+)"', response_text)
    return m.group(1) if m else ""


class PublicUser(HttpUser):
    """Simulates an unauthenticated visitor browsing public pages."""
    wait_time = between(1, 3)

    @task(3)
    def home(self):
        self.client.get("/")

    @task(2)
    def courses(self):
        self.client.get("/courses")

    @task(1)
    def about(self):
        self.client.get("/about")

    @task(1)
    def login_page(self):
        self.client.get("/login")


class CoupleUser(HttpUser):
    """Simulates a registered couple logging in and using the dashboard."""
    wait_time = between(2, 5)

    def on_start(self):
        """Log in before running tasks."""
        r = self.client.get("/login")
        csrf = _csrf(r.text)
        self.client.post("/login", data={
            "registration_number": "CA-2026-0001",  # use a real test account
            "password": "TestPassword123",
            "csrf_token": csrf,
        }, allow_redirects=True)

    @task(5)
    def dashboard(self):
        self.client.get("/dashboard")

    @task(3)
    def resources(self):
        self.client.get("/resources")

    @task(2)
    def sessions(self):
        self.client.get("/sessions")

    @task(1)
    def profile(self):
        self.client.get("/profile")


class AdminUser(HttpUser):
    """Simulates an admin user using the admin panel."""
    wait_time = between(2, 5)

    def on_start(self):
        r = self.client.get("/admin/login")
        csrf = _csrf(r.text)
        self.client.post("/admin/login", data={
            "email": "admin@example.com",  # use a real test admin
            "password": "AdminPassword123",
            "csrf_token": csrf,
        }, allow_redirects=True)

    @task(3)
    def admin_dashboard(self):
        self.client.get("/admin")

    @task(2)
    def admin_users(self):
        self.client.get("/admin/users")

    @task(1)
    def admin_resources(self):
        self.client.get("/admin/resources")
