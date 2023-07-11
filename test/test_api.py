import json
from unittest.mock import patch

from fastapi.testclient import TestClient
from mongomock import MongoClient

from guid_slurp.main import app  # Replace with your actual imports
from guid_slurp.database_sync import MONGODB_COLLECTION, MONGODB_DATABASE

client = TestClient(app)


def setup_mongo_mock():
    """
    Setup the mongo mocks
    """
    mock_mongo_client = MongoClient()
    mock_db = mock_mongo_client[MONGODB_DATABASE]
    mock_collection = mock_db[MONGODB_COLLECTION]
    with open("test/test_data/podcastGuidUrl.guidUrl.json") as f:
        mock_collection_data = json.load(f)

    mock_collection.insert_many(mock_collection_data)

    return mock_mongo_client, mock_collection


def test_resolve_root():
    mock_mongo_client, mock_collection = setup_mongo_mock()

    with patch("guid_slurp.main.MongoClient") as mock:
        mock.return_value = mock_mongo_client
        # Valid URL test
        response = client.get("/?guid=856cd618-7f34-57ea-9b84-3600f1f65e7f")
        assert response.status_code == 200
        json_resp = response.json()
        assert json_resp[0].get("url") == "http://feed.nashownotes.com/rss.xml"
        assert json_resp[0].get("podcastGuid") == "856cd618-7f34-57ea-9b84-3600f1f65e7f"

        # Valid URL test
        response = client.get("/?url=http://feed.nashownotes.com/rss.xml")
        assert response.status_code == 200
        json_resp = response.json()
        assert json_resp[0].get("url") == "http://feed.nashownotes.com/rss.xml"
        assert json_resp[0].get("podcastGuid") == "856cd618-7f34-57ea-9b84-3600f1f65e7f"

        # Invalid GUID test
        response = client.get("/?guid=not-a-valid-uuid")
        assert response.status_code == 404
        # assert response.json()["detail"][0]["type"] == "type_error.uuid"

        # Invalid URL test
        response = client.get("/?url=not-a-valid-url")
        assert response.status_code == 404
        # assert response.json()["detail"][0]["type"] == "value_error.url.scheme"

        # empty GUID and URL test
        response = client.get("/")
        assert response.status_code == 404
        assert response.json()["detail"] == "Item not found"


def test_resolve_guid():
    # Create a mock MongoClient
    mock_mongo_client, mock_collection = setup_mongo_mock()

    # Patch MongoClient
    with patch(
        "guid_slurp.main.MongoClient"
    ) as mock:  # Replace 'your_app' with the module where MongoClient is imported
        mock.return_value = mock_mongo_client
        # Valid URL test
        response = client.get("/guid/856cd618-7f34-57ea-9b84-3600f1f65e7f")
        assert response.status_code == 200
        json_resp = response.json()
        assert json_resp[0].get("url") == "http://feed.nashownotes.com/rss.xml"
        assert json_resp[0].get("podcastGuid") == "856cd618-7f34-57ea-9b84-3600f1f65e7f"

        # Invalid URL test
        response = client.get("/guid/not-a-valid-uuid")
        assert response.status_code == 404
        # assert response.json()["detail"][0]["type"] == "type_error.uuid"

        # Not found test
        mock_collection.delete_many({})  # No results found
        response = client.get("/guid/1a4e9748-4296-5a32-b017-bd36bb47e17d")
        assert response.status_code == 404
        assert response.json() == {"detail": "Item not found"}


def test_resolve_url():
    # Create a mock MongoClient
    mock_mongo_client, mock_collection = setup_mongo_mock()

    # Patch MongoClient
    with patch(
        "guid_slurp.main.MongoClient"
    ) as mock:  # Replace 'your_app' with the module where MongoClient is imported
        mock.return_value = mock_mongo_client
        # Valid URL test
        response = client.get("/url/?url=http://feed.nashownotes.com/rss.xml")
        assert response.status_code == 200
        json_resp = response.json()
        assert json_resp[0].get("url") == "http://feed.nashownotes.com/rss.xml"
        assert json_resp[0].get("podcastGuid") == "856cd618-7f34-57ea-9b84-3600f1f65e7f"

        # Invalid URL test
        response = client.get("/url/?url=not-a-valid-url")
        assert response.status_code == 422
        assert response.json()["detail"][0]["type"] == "url_parsing"

        # Not found test
        mock_collection.delete_many({})  # No results found
        response = client.get("/url/?url=https://example.com/not_found.rss")
        assert response.status_code == 404
        assert response.json() == {"detail": "Item not found"}


def test_resolve_itunesId():
    # Create a mock MongoClient
    mock_mongo_client, mock_collection = setup_mongo_mock()

    # Patch MongoClient
    with patch(
        "guid_slurp.main.MongoClient"
    ) as mock:  # Replace 'your_app' with the module where MongoClient is imported
        mock.return_value = mock_mongo_client
        # Valid URL test
        response = client.get("/itunesId/269169796")
        assert response.status_code == 200
        json_resp = response.json()
        assert json_resp[0].get("url") == "http://feed.nashownotes.com/rss.xml"
        assert json_resp[0].get("podcastGuid") == "856cd618-7f34-57ea-9b84-3600f1f65e7f"

        # Invalid URL test
        response = client.get("/itunesId/not-a-valid-id")
        assert response.status_code == 422
        assert response.json()["detail"][0]["type"] == "int_parsing"

        # Not found test
        mock_collection.delete_many({})  # No results found
        response = client.get("/itunesId/9999999")
        assert response.status_code == 404
        assert response.json() == {"detail": "Item not found"}
