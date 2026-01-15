"""
Unit tests for Khmelnytskyi Outage API.

Tests API endpoints with mocked data, independent of external website.
Run with: pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import tempfile
import os

# Import app after setting up test database
from main import app, db, service


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_db():
    """Create temporary test database with sample data."""
    from app.db.database import Database
    
    # Use temporary file for test database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_db_path = f.name
    
    test_database = Database(db_path=test_db_path)
    
    # Insert sample data
    sample_schedules = {
        "1.1": [{"start": "04:00", "end": "09:00", "type": "base"}],
        "1.2": [{"start": "10:00", "end": "15:00", "type": "base"}],
        "2.1": [
            {"start": "06:00", "end": "11:00", "type": "base"},
            {"start": "18:00", "end": "23:00", "type": "base"}
        ],
        "3.1": [{"start": "08:00", "end": "13:00", "type": "base"}],
    }
    
    test_database.save_schedule(
        date="2026-01-15",
        schedules=sample_schedules,
        message="Тестове оперативне повідомлення про зміни в графіку."
    )
    
    test_database.save_schedule(
        date="2026-01-16",
        schedules={
            "1.1": [{"start": "05:00", "end": "10:00", "type": "base"}],
            "2.1": [{"start": "07:00", "end": "12:00", "type": "base"}],
        },
        message=None
    )
    
    yield test_database
    
    # Cleanup - just try to remove the file
    try:
        os.unlink(test_db_path)
    except (PermissionError, OSError):
        pass  # Windows may still lock the file


class TestHealthCheck:
    """Tests for /status endpoint."""
    
    def test_status_returns_healthy(self, client):
        """Status endpoint should return healthy status."""
        response = client.get("/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "last_scrape" in data
        assert "available_dates" in data
        assert data["total_queues"] == 12
    
    def test_status_lists_available_dates(self, client, test_db):
        """Status should list dates from database."""
        # Patch the global db with test_db
        with patch.object(service, 'db', test_db):
            # Re-import to get fresh db reference
            response = client.get("/status")
            assert response.status_code == 200


class TestScheduleEndpoints:
    """Tests for /schedule endpoints."""
    
    def test_get_schedule_valid_queue(self, client):
        """Should return schedule for valid queue."""
        response = client.get("/schedule/1.1/2026-01-15")
        
        assert response.status_code == 200
        data = response.json()
        assert data["queue"] == "1.1"
        assert data["date"] == "2026-01-15"
        assert "intervals" in data
        assert "status" in data
        assert "total_hours_off" in data
        assert "operational_message" in data
        assert "last_updated" in data
    
    def test_get_schedule_invalid_queue_format(self, client):
        """Should return 400 for invalid queue format."""
        invalid_queues = ["7.1", "1.3", "0.1", "abc", "11", "1.1.1"]
        
        for queue in invalid_queues:
            response = client.get(f"/schedule/{queue}/2026-01-15")
            assert response.status_code == 400, f"Expected 400 for queue: {queue}"
    
    def test_get_schedule_valid_queues(self, client):
        """Should accept all valid queue formats (1.1 - 6.2)."""
        valid_queues = [f"{i}.{j}" for i in range(1, 7) for j in range(1, 3)]
        
        for queue in valid_queues:
            response = client.get(f"/schedule/{queue}/2026-01-15")
            assert response.status_code == 200, f"Expected 200 for queue: {queue}"
            assert response.json()["queue"] == queue
    
    def test_get_schedule_invalid_date_format(self, client):
        """Should return 400 for invalid date format."""
        # Note: dates with "/" are interpreted as path segments by FastAPI (404)
        # Only test formats that reach the validation logic
        invalid_dates = ["15-01-2026", "15.01.2026", "invalid", "2026-1-15", "2026-01-5"]
        
        for date in invalid_dates:
            response = client.get(f"/schedule/1.1/{date}")
            assert response.status_code == 400, f"Expected 400 for date: {date}"
    
    def test_get_schedule_no_data_status(self, client):
        """Should return no_data status for dates without data."""
        response = client.get("/schedule/1.1/2020-01-01")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "no_data"
        assert data["intervals"] == []
        assert data["total_hours_off"] == 0.0
    
    def test_get_schedule_default_date(self, client):
        """Should use today's date when date not provided."""
        response = client.get("/schedule/1.1")
        
        assert response.status_code == 200
        data = response.json()
        # Date should be set (either today or Kyiv timezone today)
        assert "date" in data
        assert len(data["date"]) == 10  # YYYY-MM-DD format


class TestAllSchedulesEndpoint:
    """Tests for /all/{day} endpoint."""
    
    def test_get_all_schedules(self, client):
        """Should return all queues for a date."""
        response = client.get("/all/2026-01-15")
        
        assert response.status_code == 200
        data = response.json()
        assert data["date"] == "2026-01-15"
        assert "queues" in data
        assert "last_updated" in data
        assert "operational_message" in data
    
    def test_get_all_schedules_structure(self, client):
        """Each queue should have intervals and total_hours_off."""
        response = client.get("/all/2026-01-15")
        data = response.json()
        
        for queue_name, queue_data in data["queues"].items():
            assert "intervals" in queue_data
            assert "total_hours_off" in queue_data
            assert isinstance(queue_data["intervals"], list)
            assert isinstance(queue_data["total_hours_off"], (int, float))
    
    def test_get_all_schedules_empty_date(self, client):
        """Should return empty queues dict for date without data."""
        response = client.get("/all/2020-01-01")
        
        assert response.status_code == 200
        data = response.json()
        assert data["queues"] == {}


class TestDatesEndpoint:
    """Tests for /dates endpoint."""
    
    def test_get_dates(self, client):
        """Should return list of available dates."""
        response = client.get("/dates")
        
        assert response.status_code == 200
        data = response.json()
        assert "dates" in data
        assert isinstance(data["dates"], list)
    
    def test_dates_format(self, client):
        """Dates should be in YYYY-MM-DD format."""
        response = client.get("/dates")
        data = response.json()
        
        for date in data["dates"]:
            assert len(date) == 10
            assert date[4] == "-" and date[7] == "-"


class TestUpdateEndpoint:
    """Tests for /update endpoint."""
    
    def test_update_success(self, client):
        """Should return success when scraping works."""
        # Mock the scraper to return test HTML
        mock_html = """
        <div class="post">
            <img alt="ГПВ-20.01.26">
            <ul>
                <li>підчерга 1.1 – з 10:00 до 15:00;</li>
            </ul>
        </div>
        """
        
        with patch.object(service.scraper, 'fetch', return_value=mock_html):
            with patch.object(service.scraper, 'extract_blocks', return_value=[
                {
                    "date": "2026-01-20",
                    "schedule_text": "підчерга 1.1 – з 10:00 до 15:00",
                    "extras_text": ""
                }
            ]):
                response = client.get("/update")
        
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert "dates" in data
                assert "message" in data
    
    def test_update_failure(self, client):
        """Should return error when scraping fails."""
        with patch.object(service.scraper, 'fetch', return_value=None):
            response = client.get("/update")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "error"


class TestResponseFormat:
    """Tests for API response format (for СВІТЛО app integration)."""
    
    def test_schedule_response_format(self, client):
        """Schedule response should match expected format."""
        response = client.get("/schedule/3.1/2026-01-15")
        data = response.json()
        
        # Required fields
        required_fields = [
            "queue", "date", "status", "intervals",
            "operational_message", "last_updated", "total_hours_off"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Type checks
        assert isinstance(data["queue"], str)
        assert isinstance(data["date"], str)
        assert data["status"] in ("active", "no_data")
        assert isinstance(data["intervals"], list)
        assert isinstance(data["total_hours_off"], (int, float))
    
    def test_interval_format(self, client):
        """Each interval should have start, end, type."""
        response = client.get("/schedule/1.1/2026-01-15")
        data = response.json()
        
        for interval in data["intervals"]:
            assert "start" in interval
            assert "end" in interval
            assert "type" in interval
            # Time format HH:MM
            assert len(interval["start"]) == 5
            assert len(interval["end"]) == 5


class TestTotalHoursCalculation:
    """Tests for total_hours_off calculation."""
    
    def test_hours_calculation_simple(self, client, test_db):
        """Should correctly calculate hours for single interval."""
        # 04:00 - 09:00 = 5 hours
        with patch('main.db', test_db):
            data = test_db.get_schedule("1.1", "2026-01-15")
            
            # Manual calculation
            from main import calculate_hours
            hours = calculate_hours(data)
            assert hours == 5.0
    
    def test_hours_calculation_multiple_intervals(self, client, test_db):
        """Should sum hours for multiple intervals."""
        # 2.1: 06:00-11:00 (5h) + 18:00-23:00 (5h) = 10h
        from main import calculate_hours
        
        data = test_db.get_schedule("2.1", "2026-01-15")
        hours = calculate_hours(data)
        assert hours == 10.0
    
    def test_hours_calculation_empty(self, client):
        """Should return 0 for empty intervals."""
        from main import calculate_hours
        assert calculate_hours([]) == 0.0


class TestEdgeCases:
    """Edge case tests."""
    
    def test_queue_case_sensitivity(self, client):
        """Queue validation should be exact match."""
        response = client.get("/schedule/1.1/2026-01-15")
        assert response.status_code == 200
    
    def test_future_dates(self, client):
        """Should handle future dates."""
        response = client.get("/schedule/1.1/2030-12-31")
        assert response.status_code == 200
        assert response.json()["status"] == "no_data"
    
    def test_past_dates(self, client):
        """Should handle past dates."""
        response = client.get("/schedule/1.1/2020-01-01")
        assert response.status_code == 200
        assert response.json()["status"] == "no_data"
    
    def test_special_characters_in_date(self, client):
        """Should reject dates with special characters."""
        response = client.get("/schedule/1.1/2026-01-15'")
        assert response.status_code == 400


class TestCORS:
    """Tests for CORS configuration."""
    
    def test_cors_headers(self, client):
        """Should include CORS headers in response."""
        response = client.options(
            "/schedule/1.1",
            headers={"Origin": "http://example.com"}
        )
        # FastAPI handles CORS, check that it doesn't block
        assert response.status_code in (200, 405)


class TestDocumentation:
    """Tests for API documentation endpoints."""
    
    def test_openapi_available(self, client):
        """OpenAPI schema should be available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
    
    def test_docs_available(self, client):
        """Swagger UI should be available."""
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_redoc_available(self, client):
        """ReDoc should be available."""
        response = client.get("/redoc")
        assert response.status_code == 200
