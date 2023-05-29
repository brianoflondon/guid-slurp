from pymongo import MongoClient
from pymongo.mongo_client import MongoClient as MongoClientType

MONGODB_CONNECTION = "mongodb://localhost:27017"
MONGODB_DATABASE = "podcastGuidUrl"
MONGODB_COLLECTION = "guidUrl"


def check_connection(connection: str):
    """
    Check the connection to MongoDB
    :param connection: MongoDB connection string
    :return: True if connection is successful
    """
    client = MongoClient(connection)  # type: MongoClientType
    try:
        # The ismaster command is cheap and does not require auth.
        client.admin.command("ismaster")
    except Exception as e:
        print(f"Connection error: {str(e)}")
        return False
    else:
        print("Connection successful.")
        return True
    finally:
        client.close()
