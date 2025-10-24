import pytest
import json

# --- Imports are now simpler ---
from app import app, db, bcrypt, User, Semester, Subject, Grade

# ----------------------------------------------------
#       The entire custom FlaskClient class is GONE
# ----------------------------------------------------

# ----------------------------------------------------
#                  PYTEST FIXTURES
# ----------------------------------------------------

@pytest.fixture(scope='function')
def client():
    """
    Fixture to configure the app for testing and provide a clean database
    and a standard test client instance.
    """
    app.config.update({
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "TESTING": True, # This is the flag that disables CSRF in app.py
        "SECRET_KEY": "test-secret-key-for-sessions",
    })

    with app.app_context():
        db.create_all()

    test_client = app.test_client()
    yield test_client

    with app.app_context():
        db.drop_all()


@pytest.fixture(scope='function')
def auth_client(client):
    """
    Fixture that creates a user and provides a logged-in client
    by directly manipulating the session. This is fast and reliable.
    """
    with app.app_context():
        test_user_password = "password123"
        hashed_password = bcrypt.generate_password_hash(test_user_password).decode('utf-8')
        
        test_user = User(
            username="testuser",
            email="test@example.com",
            password=hashed_password
        )
        db.session.add(test_user)
        db.session.commit()

        # --- THE FIX for 302/401 Errors ---
        # Set 'username' in the session to match the @login_required decorator.
        with client.session_transaction() as sess:
            sess['username'] = test_user.username

        yield {
            "client": client,
            "user": test_user,
        }

# ----------------------------------------------------
#                  PYTEST SUITE
# ----------------------------------------------------

def test_index_route_access(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b"Tip of the Day" in response.data

def test_login_page_access(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert b"Login" in response.data

def test_successful_login_and_logout(client):
    """
    Tests the full login/logout flow now that CSRF is disabled for tests.
    """
    # Create a user to log in with
    with app.app_context():
        hashed_password = bcrypt.generate_password_hash("password123").decode('utf-8')
        user = User(username="login_test", email="login@test.com", password=hashed_password)
        db.session.add(user)
        db.session.commit()

    # Test login
    response = client.post('/login', data={
        "username": "login_test",
        "password": "password123"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Tip of the Day" in response.data # Should be on home page

    # Test that a protected page is now accessible
    response = client.get('/noten')
    assert response.status_code == 200
    assert b"Semester Management" in response.data

    # Test logout
    response = client.get('/logout', follow_redirects=True)
    assert response.status_code == 200
    assert b"Tip of the Day" in response.data

def test_grades_protected_route_unauthenticated(client):
    response = client.get('/noten', follow_redirects=False)
    assert response.status_code == 302
    assert '/login' in response.headers['Location']

def test_grades_protected_route_authenticated(auth_client):
    client = auth_client['client']
    response = client.get('/noten')
    assert response.status_code == 200
    assert b"Semester Management" in response.data

def test_api_grades_endpoint_post(auth_client):
    client = auth_client['client']
    user = auth_client['user']
    
    with app.app_context():
        test_semester = Semester(user_id=user.id, name="API Test Semester")
        db.session.add(test_semester)
        db.session.commit()
        test_semester_id = test_semester.id

    new_grade_data = [{
        "semester_id": test_semester_id,
        "name": "Midterm Exam",
        "subjects": [{"name": "History", "counts_towards_average": True, "grades": []}]
    }]

    # --- SIMPLIFIED POST ---
    # No need for CSRF tokens or special helpers.
    response = client.post(
        '/api/noten',
        data=json.dumps(new_grade_data),
        content_type='application/json'
    )

    assert response.status_code == 200
    assert response.get_json()['status'] == 'success'

    with app.app_context():
        new_subject = Subject.query.filter_by(name="History").first()
        assert new_subject is not None
        assert new_subject.semester_id == test_semester_id

