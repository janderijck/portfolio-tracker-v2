"""Tests for the health-check / root endpoint."""


def test_root_returns_200(client):
    """GET / should return 200 with a status message."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "running"
    assert "Portfolio Tracker" in data["message"]
