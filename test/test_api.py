from unittest.mock import patch

from fastapi.testclient import TestClient
from mongomock import MongoClient

from guid_slurp.main import app  # Replace with your actual imports
from guid_slurp.startup import MONGODB_COLLECTION, MONGODB_DATABASE

client = TestClient(app)


def test_resolve_guid():
    # Create a mock MongoClient
    mock_mongo_client = MongoClient()
    mock_db = mock_mongo_client[MONGODB_DATABASE]
    mock_collection = mock_db[MONGODB_COLLECTION]

    one_record = {
        "url": "https://example.com/feed.rss",
        "podcastGuid": "02e12f05-9dc2-4b28-b604-662d7507d435",
    }

    # Add a mock result
    mock_collection.insert_one(one_record)

    # Patch MongoClient
    with patch(
        "guid_slurp.main.MongoClient"
    ) as mock:  # Replace 'your_app' with the module where MongoClient is imported
        mock.return_value = mock_mongo_client
        # Valid URL test
        response = client.get("/guid/02e12f05-9dc2-4b28-b604-662d7507d435")
        assert response.status_code == 200
        json_resp = response.json()
        assert json_resp[0].get("url") == "https://example.com/feed.rss"
        assert json_resp[0].get("podcastGuid") == "02e12f05-9dc2-4b28-b604-662d7507d435"

        # Invalid URL test
        response = client.get("/guid/not-a-valid-uuid")
        assert response.status_code == 400
        assert response.json() == {"detail": "Bad GUID"}

        # Not found test
        mock_collection.delete_many({})  # No results found
        response = client.get("/guid/02e12f05-9dc2-4b28-b604-662d7507d436")
        assert response.status_code == 404
        assert response.json() == {"detail": "Item not found"}


def test_resolve_url():
    # Create a mock MongoClient
    mock_mongo_client = MongoClient()
    mock_db = mock_mongo_client[MONGODB_DATABASE]
    mock_collection = mock_db[MONGODB_COLLECTION]

    one_record = {
        "url": "https://example.com/feed.rss",
        "podcastGuid": "02e12f05-9dc2-4b28-b604-662d7507d435",
    }

    # Add a mock result
    mock_collection.insert_one(one_record)

    # Patch MongoClient
    with patch(
        "guid_slurp.main.MongoClient"
    ) as mock:  # Replace 'your_app' with the module where MongoClient is imported
        mock.return_value = mock_mongo_client
        # Valid URL test
        response = client.get("/url/?url=https://example.com/feed.rss")
        assert response.status_code == 200
        json_resp = response.json()
        assert json_resp[0].get("url") == "https://example.com/feed.rss"
        assert json_resp[0].get("podcastGuid") == "02e12f05-9dc2-4b28-b604-662d7507d435"

        # Invalid URL test
        response = client.get("/url/?url=not-a-valid-url")
        assert response.status_code == 400
        assert response.json() == {"detail": "Bad RSS URL"}

        # Not found test
        mock_collection.delete_many({})  # No results found
        response = client.get("/url/?url=https://example.com/not_found.rss")
        assert response.status_code == 404
        assert response.json() == {"detail": "Item not found"}
