"""
Unit tests for model methods. These are pure in-memory tests —
no database writes, no HTTP requests.
"""
from models import User, _generate_registration_number


class TestUserPassword:
    def test_set_and_check_correct_password(self):
        u = User(email='a@test.com')
        u.set_password('StrongPass123!')
        assert u.check_password('StrongPass123!') is True

    def test_wrong_password_fails(self):
        u = User(email='b@test.com')
        u.set_password('correct')
        assert u.check_password('wrong') is False

    def test_hash_is_not_plaintext(self):
        u = User(email='c@test.com')
        u.set_password('mypassword')
        assert 'mypassword' not in u.password_hash


class TestUserCoupleName:
    def test_both_names(self):
        u = User(bride_first_name='Mary', groom_first_name='Joseph')
        name = u.get_couple_name()
        assert 'Mary' in name
        assert 'Joseph' in name

    def test_bride_only(self):
        u = User(bride_first_name='Mary')
        name = u.get_couple_name()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_groom_only(self):
        u = User(groom_first_name='Joseph')
        name = u.get_couple_name()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_empty_returns_string(self):
        u = User()
        name = u.get_couple_name()
        assert isinstance(name, str)


class TestUserPreferences:
    def test_defaults_returned_when_no_prefs_set(self):
        u = User()
        prefs = u.get_preferences()
        assert prefs['theme'] == 'system'
        assert prefs['email_notifications'] is True
        assert prefs['compact_mode'] is False

    def test_set_theme_preference(self):
        u = User()
        u.set_preference('theme', 'dark')
        assert u.get_preferences()['theme'] == 'dark'

    def test_set_notifications_preference(self):
        u = User()
        u.set_preference('email_notifications', False)
        assert u.get_preferences()['email_notifications'] is False

    def test_unset_keys_use_defaults(self):
        u = User()
        u.set_preference('theme', 'light')
        prefs = u.get_preferences()
        assert 'email_notifications' in prefs
        assert 'compact_mode' in prefs

    def test_invalid_json_returns_defaults(self):
        u = User()
        u.preferences = 'not valid json {{{'
        prefs = u.get_preferences()
        assert prefs['theme'] == 'system'

    def test_none_preferences_returns_defaults(self):
        u = User()
        u.preferences = None
        prefs = u.get_preferences()
        assert isinstance(prefs, dict)
        assert len(prefs) == 3


class TestRegistrationNumber:
    def test_format(self):
        rn = _generate_registration_number()
        assert rn.startswith('COR-')

    def test_structure(self):
        rn = _generate_registration_number()
        parts = rn.split('-')
        assert len(parts) == 3
        assert parts[0] == 'COR'
        assert len(parts[1]) == 4      # year
        assert parts[1].isdigit()
        assert len(parts[2]) == 4      # suffix
        assert parts[2].isdigit()

    def test_uniqueness(self):
        numbers = {_generate_registration_number() for _ in range(50)}
        # Collision probability with 4-digit suffix is very low
        assert len(numbers) >= 40


class TestUserFlags:
    def test_default_flags(self):
        u = User(email='x@test.com')
        u.set_password('pass')
        assert u.is_paid is False or u.is_paid is None
        assert u.is_admin is False or u.is_admin is None

    def test_user_is_not_admin_by_default(self):
        u = User(email='y@test.com', is_admin=False)
        assert not u.is_admin
