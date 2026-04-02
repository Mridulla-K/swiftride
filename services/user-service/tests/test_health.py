import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app

client = TestClient(app)

@pytest.fixture
def mock_db():
    with patch("app.routes.get_db", new_callable=AsyncMock) as mock_db:
        yield mock_db

def test_user_registration(mock_db):
    payload = {
        "email": f"test-{uuid.uuid4()}@example.com",
        "password": "secure-password",
        "full_name": "Test User",
        "phone": "+1234567890"
    }
    
    # Mock behavior to show email not registered
    mock_db.execute.return_value = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    
    # Mock user creation
    with patch("app.routes.User") as mock_user_cls:
        mock_user = mock_user_cls.return_value
        mock_user.id = uuid.uuid4()
        mock_user.email = payload["email"]
        mock_user.full_name = payload["full_name"]
        mock_user.phone = payload["phone"]

        response = client.post("/api/v1/users/register", json=payload)
        
        assert response.status_code == 201
        assert "id" in response.json()
        assert response.json()["email"] == payload["email"]

def test_duplicate_registration_returns_409(mock_db):
    payload = {
        "email": "existing@example.com",
        "password": "secure-password",
        "full_name": "Existing User",
        "phone": "+1234567890"
    }
    
    # Mock behavior to show email ALREADY registered
    mock_db.execute.return_value = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = True
    
    response = client.post("/api/v1/users/register", json=payload)
    
    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"

def test_user_login_returns_jwt(mock_db):
    payload = {
        "email": "test@example.com",
        "password": "correct-password"
    }
    
    # Mock user retrieval and password verification
    with patch("app.routes.User") as mock_user_cls:
        mock_user = mock_user_cls.return_value
        mock_user.id = uuid.uuid4()
        mock_user.email = payload["email"]
        mock_user.hashed_password = "hashed-correct-password"
        
        mock_db.execute.return_value = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_user
        
        with patch("app.routes._verify_password", return_value=True):
            response = client.post("/api/v1/users/login", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
