import asyncio
import csv
import logging
import os
import sqlite3
import tarfile
import tempfile
from datetime import datetime, timedelta, timezone
from time import mktime, strptime
from timeit import default_timer as timer
from typing import Any, List, Mapping, Sequence
from urllib.parse import urlparse

import httpx
from pydantic import UUID5, AnyUrl, BaseModel, Field
from pymongo import DESCENDING, MongoClient
from pymongo.mongo_client import MongoClient as MongoClientType
from tqdm import tqdm
from tqdm.utils import CallbackIOWrapper

MONGODB_CONNECTION = "mongodb://10.0.0.11:27017"
MONGODB_DATABASE = "podcastGuidUrl"
MONGODB_COLLECTION = "guidUrl"
MONGODB_DUPLICATES = "duplicateGuidUrl"


DIRECTORY = os.path.join(tempfile.gettempdir(), "podcastindex")
DOWNLOAD_FILENAME = "podcastindex_feeds.db.tgz"
DOWNLOAD_PATH = os.path.join(DIRECTORY, DOWNLOAD_FILENAME)
UNTAR_PATH = os.path.join(DIRECTORY, "podcastindex_feeds.db")
CSV_PATH = os.path.join(DIRECTORY, "podcasts.csv")


COUNT_LINES = 0
# Construct the path using os.path.join

# Create a logger instance
logger = logging.getLogger(__name__)


def check_database_fileinfo() -> dict[Any, Any]:
    latest_record: dict[Any:Any] = {}
    with MongoClient(MONGODB_CONNECTION) as client:  # type: MongoClientType
        db = client[MONGODB_DATABASE]
        latest_record = db["fileInfo"].find_one(sort=[("timestamp", DESCENDING)])
    return latest_record


def write_database_fileinfo(headers: dict[Any, Any]):
    with MongoClient(MONGODB_CONNECTION) as client:  # type: MongoClientType
        db = client[MONGODB_DATABASE]
        timestamp = datetime.now(timezone.utc)
        db["fileInfo"].insert_one(
            {
                "Content-Length": headers.get("Content-Length"),
                "Last-Modified": headers.get("Last-Modified"),
                "etag": headers.get("etag"),
                "timestamp": timestamp,
            }
        )


def check_new_podcastindex_database() -> bool:
    """
    Check for a new database to download
    """
    url = f"https://public.podcastindex.org/{DOWNLOAD_FILENAME}"

    if os.path.exists(DOWNLOAD_PATH):
        logger.info(f"File already downloaded {DOWNLOAD_PATH}")
        latest_record = check_database_fileinfo()
        # Only download if the file is not already downloaded
        # Get the metadata of the remote file
        headers = {"If-None-Match": latest_record.get("etag", "")}
        response = httpx.head(url, headers=headers)
        if response.status_code == 304:
            logger.info("File is up to date")
            return False

        return True


def fetch_new_podcastindex_database():
    try:
        # Send a GET request to the URL and stream the response
        url = f"https://public.podcastindex.org/{DOWNLOAD_FILENAME}"
        with httpx.stream("GET", url) as response:
            # Get the total file size from the Content-Length header
            total_size = int(response.headers.get("Content-Length", 0))
            write_database_fileinfo(response.headers)
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
        logger.info("Error loading database")
        logger.info(ex)


def untar_file():
    # Open the tar.gz file
    CHUNK_SIZE = 1024 * 1024  # 1 MB
    if os.path.exists(UNTAR_PATH):
        logger.info(f"File already untarred {UNTAR_PATH}")
        return
    with tarfile.open(DOWNLOAD_PATH, "r:gz") as tar:
        # Get the total number of members (files/directories) in the tar file
        # Extract each member in the tar file
        logger.info("Examining tarfile ...")
        for member in tar.getmembers():
            # Open a new file for writing
            if member.name == "./podcastindex_feeds.db":
                logger.info(f"Extracting file {member.name}")
                extracted_size = 0
                with tar.extractfile(member) as source, open(
                    UNTAR_PATH, "wb"
                ) as destination:
                    with tqdm(
                        total=member.size,
                        unit="B",
                        unit_scale=True,
                        unit_divisor=1024,
                        desc=f"Extracting: {member.name}",
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
    logger.info("Number of rows:", COUNT_LINES)

    if os.path.exists(CSV_PATH):
        logger.info("CSV File already exists")
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


def create_duplicate_collection(client: MongoClient):
    """
    Create the Duplicate collection in the database
    """
    # check if collection duplicatesGuid exists
    db = client[MONGODB_DATABASE]
    if MONGODB_DUPLICATES in db.list_collection_names():
        logger.info("Collection duplicatesGuid already exists")
        return
    # Duplicates of GUID
    pipeline: Sequence[Mapping[str, Any]] = [
        {
            "$group": {
                "_id": "$podcastGuid",
                "count": {"$sum": 1},
                "duplicates": {
                    "$push": {"url": "$url", "podcastIndexId": "$podcastIndexId"}
                },
            }
        },
        {"$match": {"count": {"$gt": 1}}},
        {"$sort": {"count": -1}},
        {"$out": MONGODB_DUPLICATES},
    ]
    logger.info("Creating collection of duplicatesGuidUrl  .... slow operation")
    db[MONGODB_COLLECTION].aggregate(pipeline)
    logger.info("🟢Created collection of duplicatesGuidUrl")


class DuplicateRecord(BaseModel):
    url: AnyUrl | str
    podcastIndexId: int


class Duplicates(BaseModel):
    podcastGuid: UUID5 | str = Field("", alias="_id")
    count: int
    duplicates: List[DuplicateRecord]


def process_duplicates(client: MongoClient):
    """
    Takes the duplicate colleciton and highlights where the duplicates are
    all from the same base URL
    """
    db = client[MONGODB_DATABASE]
    collection = db[MONGODB_DUPLICATES]
    cursor = collection.find({})
    unique_url_count = {}
    logger.info("Starting the process of duplicatesGuidUrl  .... slow operation")
    for doc in cursor:
        record = Duplicates(**doc)
        all_urls = {urlparse(item.url).netloc for item in record.duplicates}
        all_podcastIds = {item.podcastIndexId for item in record.duplicates}
        # logger.info(f"Duplicates: {len(record.duplicates):>4} :  {len(all_urls)}")
        unique_url_count[record.podcastGuid] = len(all_urls)
        query = {"_id": str(record.podcastGuid)}
        update = {
            "$set": {
                "uniqueDomainCount": len(all_urls),
                "uniqueDomains": list(all_urls),
                "podcastIndexId": list(all_podcastIds),
            }
        }
        collection.update_one(query, update)
    logger.info("🟢Finished the process of duplicatesGuidUrl  .... slow operation")


def create_database():
    global COUNT_LINES
    with sqlite3.connect(UNTAR_PATH) as conn:
        c = conn.cursor()

        # Execute the query to count the rows in the table
        c.execute("SELECT COUNT(*) FROM podcasts")

        # Fetch the result and store it in a variable
        COUNT_LINES = c.fetchone()[0]

        # Print the count
        logger.info(f"Number of rows: {COUNT_LINES}")

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
                logger.info("Database already created")
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


def finish_database_import():
    """
    Finish the database import
    """
    with MongoClient(MONGODB_CONNECTION) as client:
        create_indexes(client)
        create_duplicate_collection(client)


def is_running_in_docker() -> bool:
    return os.path.exists("/.dockerenv")


def fmt_time(seconds: int) -> str:
    """
    Format the time
    """
    seconds = round(seconds, 0)
    return str(timedelta(seconds=seconds))


def setup_logging():
    # Set the logging level
    if not os.path.exists(DIRECTORY):
        # Create the directory
        os.makedirs(DIRECTORY)
        logger.info("Directory created: ", DIRECTORY)

    logger.setLevel(logging.INFO)

    # Create a formatter
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(module)-14s %(lineno) 5d : %(message)s"
    )

    # Create a handler for stdout (console)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Create a handler for the log file
    log_file_path = os.path.join(DIRECTORY, "import.log")
    file_handler = logging.FileHandler(log_file_path, mode="w")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)


def setup_paths():
    global MONGODB_CONNECTION, DIRECTORY, DOWNLOAD_FILENAME, DOWNLOAD_PATH
    global UNTAR_PATH, CSV_PATH

    if is_running_in_docker():
        MONGODB_CONNECTION = "mongodb://mongodb:27017/"
        DIRECTORY = os.path.join("data/", "podcastindex")
        DOWNLOAD_FILENAME = "podcastindex_feeds.db.tgz"
        DOWNLOAD_PATH = os.path.join(DIRECTORY, DOWNLOAD_FILENAME)
        UNTAR_PATH = os.path.join(DIRECTORY, "podcastindex_feeds.db")
        CSV_PATH = os.path.join(DIRECTORY, "podcasts.csv")

    setup_logging()


async def startup_import():
    """
    Startup import
    """
    start = timer()

    global MONGODB_CONNECTION, DIRECTORY, DOWNLOAD_FILENAME, DOWNLOAD_PATH
    global UNTAR_PATH, CSV_PATH

    in_docker = False
    if is_running_in_docker():
        in_docker = True

    logger.info("Starting import of PodcastIndex DB Dump ...")
    logger.info(f"Running in docker: {in_docker}")

    logger.info(f"MongoDB connection: {MONGODB_CONNECTION}")

    if check_new_podcastindex_database():
        fetch_new_podcastindex_database()

    logger.info(
        f"Finished downloading database                    : {fmt_time(timer()-start)}"
    )
    untar_file()
    logger.info(
        f"Finished untar                                   : {fmt_time(timer()-start)}"
    )
    create_database()
    # Remove the untarred file
    os.remove(UNTAR_PATH)
    logger.info(
        f"Finished database creation                       : {fmt_time(timer()-start)}"
    )
    finish_database_import()
    logger.info(
        f"Finished database finalisation                   : {fmt_time(timer()-start)}"
    )


async def keep_checking():
    """
    Keep checking for new database
    """
    repeat_check = 4  # hours
    setup_paths()
    while True:
        try:
            if check_new_podcastindex_database():
                await startup_import()
            logger.info(f"Sleeping for {repeat_check} hours")
            await asyncio.sleep(60 * 60 * repeat_check)
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Exiting")
            return
        except Exception as e:
            logger.error(e)


if __name__ == "__main__":
    # with MongoClient(MONGODB_CONNECTION) as client:
    #     create_duplicate_collection(client)
    #     process_duplicates(client)
    try:
        asyncio.run(keep_checking())
    except Exception as e:
        logger.error(e)
