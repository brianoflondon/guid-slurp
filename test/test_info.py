import httpx
import pytest

from guid_slurp.main import __version__, app


@pytest.mark.asyncio
async def test_info():
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        response = await client.get("/info/")
        assert response.status_code == 200
        data = response.json()

        assert data["message"] == "Guid Slurp API"
        assert data["version"] == __version__
        assert data["status"] == "OK"
        assert "time" in data

        # Additional assertions for the `file_info` if needed


@pytest.mark.asyncio
async def test_info_with_mocked_fileinfo(monkeypatch):
    # Mock the `check_database_fileinfo` function to raise an exception
    def mock_check_database_fileinfo():
        raise Exception("Database not available")

    # Apply the mock function
    monkeypatch.setattr(
        "guid_slurp.main.check_database_fileinfo", mock_check_database_fileinfo
    )

    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        response = await client.get("/info/")
        assert response.status_code == 200
        data = response.json()
        assert "file_info" in data
        assert "error" in data["file_info"]
        assert data["file_info"]["error"] == "Database not available"


# Run the tests
pytest.main()
