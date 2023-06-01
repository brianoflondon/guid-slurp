import logging

from pymongo import MongoClient
from pymongo.mongo_client import MongoClient as MongoClientType


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
        logging.info(f"Connection error: {str(e)}")
        return False
    else:
        logging.info(f"Connection successful. {connection}")
        return True
    finally:
        client.close()
