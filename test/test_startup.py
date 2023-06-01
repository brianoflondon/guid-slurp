from unittest import mock

import pytest
from pymongo import DESCENDING

from guid_slurp.database_sync import MONGODB_CONNECTION, check_database_fileinfo


@pytest.fixture(autouse=True)
def mock_mongo_client():
    with mock.patch("pymongo.MongoClient") as mock_client:
        yield mock_client


@pytest.mark.skip(reason="Not implemented yet")
def test_check_database_fileinfo(mock_mongo_client):
    # Prepare test data
    expected_result = {"timestamp": 123456789, "file_name": "test_file.txt"}

    # Mock the database query
    mock_collection = mock.Mock()
    mock_collection.find_one.return_value = expected_result
    mock_db = mock.Mock()
    mock_db.__getitem__.return_value = mock_collection
    mock_mongo_client.return_value.__getitem__.return_value = mock_db

    # Call the function under test
    result = check_database_fileinfo()

    # Assert the expected result
    assert result == expected_result
    mock_mongo_client.assert_called_once_with(MONGODB_CONNECTION)
    mock_db.__getitem__.assert_called_once_with("fileInfo")
    mock_collection.find_one.assert_called_once_with(sort=[("timestamp", DESCENDING)])
