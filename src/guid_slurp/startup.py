import csv
import logging
import os
import sqlite3
import tarfile
import tempfile
from datetime import datetime, timezone
from time import mktime, strptime
from timeit import default_timer as timer

import httpx
from pymongo import DESCENDING, MongoClient
from pymongo.mongo_client import MongoClient as MongoClientType
from tqdm import tqdm
from tqdm.utils import CallbackIOWrapper

MONGODB_CONNECTION = "mongodb://127.0.0.1:27017"
MONGODB_DATABASE = "podcastGuidUrl"
MONGODB_COLLECTION = "guidUrl"


DIRECTORY = os.path.join(tempfile.gettempdir(), "podcastindex")
DOWNLOAD_FILENAME = "podcastindex_feeds.db.tgz"
DOWNLOAD_PATH = os.path.join(DIRECTORY, DOWNLOAD_FILENAME)
UNTAR_PATH = os.path.join(DIRECTORY, "podcastindex_feeds.db")
CSV_PATH = os.path.join(DIRECTORY, "podcasts.csv")


COUNT_LINES = 0
# Construct the path using os.path.join


def check_database_fileinfo() -> dict | None:
    with MongoClient(MONGODB_CONNECTION) as client:  # type: MongoClientType
        db = client[MONGODB_DATABASE]
        latest_record = db["fileInfo"].find_one(sort=[("timestamp", DESCENDING)])
    return latest_record


def write_database_fileinfo(headers: dict):
    with MongoClient(MONGODB_CONNECTION) as client:  # type: MongoClientType
        db = client[MONGODB_DATABASE]
        timestamp = datetime.now(timezone.utc)
        db["fileInfo"].insert_one(
            {
                "Content-Length": headers.get("Content-Length"),
                "Last-Modified": headers.get("Last-Modified"),
                "timestamp": timestamp,
            }
        )


def fetch_podcastindex_database():
    url = f"https://public.podcastindex.org/{DOWNLOAD_FILENAME}"

    if not os.path.exists(DIRECTORY):
        # Create the directory
        os.makedirs(DIRECTORY)
        print("Directory created: ", DIRECTORY)

    if os.path.exists(DOWNLOAD_PATH):
        print(f"File already downloaded {DOWNLOAD_PATH}")
        latest_record = check_database_fileinfo()
        # Only download if the file is not already downloaded
        # Get the metadata of the remote file
        response = httpx.head(url)
        remote_file_size = int(response.headers.get("Content-Length"))
        remote_file_modified = response.headers.get("Last-Modified")
        write_database_fileinfo(response.headers)

        # Get the size of the local file
        file_size = os.path.getsize(DOWNLOAD_PATH)

        if (
            file_size == remote_file_size
            and latest_record
            and latest_record["Last-Modified"] == remote_file_modified
        ):
            return

    try:
        # Send a GET request to the URL and stream the response
        with httpx.stream("GET", url) as response:
            # Get the total file size from the Content-Length header
            total_size = int(response.headers.get("Content-Length", 0))

            # Open a file for writing in binary mode
            with open(DOWNLOAD_PATH, "wb") as f:
                # Wrap the write method of the file object with tqdm
                with tqdm.wrapattr(
                    f,
                    "write",
                    desc=f"Downloading: {DOWNLOAD_FILENAME}",
                    unit="B",
                    unit_scale=True,
                    total=total_size,
                ) as wrapped_file:
                    # Iterate over the response content in
                    # chunks and write them to the file
                    for chunk in response.iter_bytes(chunk_size=4096):
                        wrapped_file.write(chunk)

                    # Close the wrapped file object
                    wrapped_file.close()
            # Get the web modified time
            web_modified = response.headers.get("Last-Modified")
            web_modified_timestamp = mktime(
                strptime(web_modified, "%a, %d %b %Y %H:%M:%S %Z")
            )

            # Set the modified time of the local file
            os.utime(DOWNLOAD_PATH, (web_modified_timestamp, web_modified_timestamp))

    except Exception as ex:
        print("Error loading database")
        print(ex)


def untar_file():
    # Open the tar.gz file
    CHUNK_SIZE = 1024 * 1024  # 1 MB
    if os.path.exists(UNTAR_PATH):
        print(f"File already untarred {UNTAR_PATH}")
        return
    with tarfile.open(DOWNLOAD_PATH, "r:gz") as tar:
        # Get the total number of members (files/directories) in the tar file
        # Extract each member in the tar file
        print("Examining tarfile ...")
        for member in tar.getmembers():
            # Open a new file for writing
            if member.name == "./podcastindex_feeds.db":
                print(f"Extracting file {member.name}")
                extracted_size = 0
                with tar.extractfile(member) as source, open(
                    UNTAR_PATH, "wb"
                ) as destination:
                    with tqdm(
                        total=member.size, unit="B", unit_scale=True, unit_divisor=1024
                    ) as t:
                        fobj = CallbackIOWrapper(t.update, source, "read")

                        while extracted_size < member.size:
                            # Read a chunk of data from the source file
                            chunk = fobj.read(CHUNK_SIZE)
                            if not chunk:
                                break

                            # Write the chunk to the destination file
                            destination.write(chunk)

                            # Update the extracted size
                            extracted_size += len(chunk)


def decode_sql():
    # Connect to the database
    global COUNT_LINES
    conn = sqlite3.connect(UNTAR_PATH)
    c = conn.cursor()

    # Execute the query to count the rows in the table
    c.execute("SELECT COUNT(*) FROM podcasts")

    # Fetch the result and store it in a variable
    COUNT_LINES = c.fetchone()[0]

    # Print the count
    print("Number of rows:", COUNT_LINES)

    if os.path.exists(CSV_PATH):
        print("CSV File already exists")
        return
    # Execute the query to select the fields from the table
    c.execute(
        "SELECT podcastGuid, url, originalUrl, id as podcastIndexId, itunesId FROM podcasts"
    )

    # Write the rows to a CSV file using an iterator

    with open(CSV_PATH, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(
            ["podcastGuid", "url", "originalUrl", "podcastIndexId", "itunesId"]
        )  # Write the header row
        for row in tqdm(c, total=COUNT_LINES, desc="Creating CSV file", unit="rows"):
            writer.writerow(row)

    # Close the database connection
    conn.close()


def create_indexes(client: MongoClient):
    # Connect to MongoDB
    db = client[MONGODB_DATABASE]

    # Access the collection
    collection = db[MONGODB_COLLECTION]

    # Create an index
    index_key = "podcastGuid"
    index_name = "podcastGuid"
    collection.create_index([(index_key, 1)], name=index_name)

    # Create an index
    index_key = "url"
    index_name = "url"
    collection.create_index([(index_key, 1)], name=index_name)

    # Create an index
    index_key = "podcastIndexId"
    index_name = "podcastIndexId"
    collection.create_index([(index_key, 1)], name=index_name)

    # Create an index
    index_key = "itunesId"
    index_name = "itunesId"
    collection.create_index([(index_key, 1)], name=index_name)


def create_database():
    global COUNT_LINES
    with sqlite3.connect(UNTAR_PATH) as conn:
        c = conn.cursor()

        # Execute the query to count the rows in the table
        c.execute("SELECT COUNT(*) FROM podcasts")

        # Fetch the result and store it in a variable
        COUNT_LINES = c.fetchone()[0]

        # Print the count
        print("Number of rows:", COUNT_LINES)

        # Execute the query to select the fields from the table
        c.execute(
            "SELECT podcastGuid, url, originalUrl, id as podcastIndexId, itunesId FROM podcasts"
        )

        # Connect to MongoDB
        with MongoClient(MONGODB_CONNECTION) as client:
            db = client[MONGODB_DATABASE]

            # Access the collection
            collection = db[MONGODB_COLLECTION]

            if COUNT_LINES == collection.count_documents({}):
                print("Database already created")
                return

            # Delete all data in the collection
            collection.drop()

            # Chunk size for batch insert
            chunk_size = 1000

            # Read the CSV file and insert data in chunks
            data = []
            timestamp = datetime.now(timezone.utc)

            for row in tqdm(c, desc="Inserting Data", total=COUNT_LINES, unit="rows"):
                data_item = {
                    "podcastGuid": row[0],
                    "url": row[1],
                    "originalUrl": row[2],
                    "podcastIndexId": row[3],
                    "itunesId": row[4],
                    "timestamp": timestamp,
                }

                data.append(data_item)

                # Insert data in chunks
                if len(data) == chunk_size:
                    collection = db[MONGODB_COLLECTION]
                    collection.insert_many(data)
                    data = []  # Clear the data list after inserting a chunk

            # Insert remaining data (less than chunk size) if any
            if data:
                collection = db[MONGODB_COLLECTION]
                collection.insert_many(data)

            # Create indexes
            create_indexes(client)


def is_running_in_docker() -> bool:
    return os.path.exists("/.dockerenv")


def startup_import():
    """
    Startup import
    """
    start = timer()
    print("Starting import of PodcastIndex DB Dump ...")

    global MONGODB_CONNECTION, DIRECTORY, DOWNLOAD_FILENAME, DOWNLOAD_PATH
    global UNTAR_PATH, CSV_PATH

    if is_running_in_docker():
        print("Running in Docker")
        MONGODB_CONNECTION = "mongodb://mongodb:27017/"
        DIRECTORY = os.path.join("data/", "podcastindex")
        DOWNLOAD_FILENAME = "podcastindex_feeds.db.tgz"
        DOWNLOAD_PATH = os.path.join(DIRECTORY, DOWNLOAD_FILENAME)
        UNTAR_PATH = os.path.join(DIRECTORY, "podcastindex_feeds.db")
        CSV_PATH = os.path.join(DIRECTORY, "podcasts.csv")

    print(f"MongoDB connection: {MONGODB_CONNECTION}")

    fetch_podcastindex_database()
    print(f"Finished downloading database: {timer()-start:.3f} seconds")
    untar_file()
    print(f"Finished untar               : {timer()-start:.3f} seconds")
    # decode_sql()
    # print(f"Finished decode SQL          : {timer()-start:.3f} seconds")
    create_database()
    # Remove the untarred file
    os.remove(UNTAR_PATH)
    print(f"Finished database creation   : {timer()-start:.3f} seconds")


if __name__ == "__main__":
    startup_import()
