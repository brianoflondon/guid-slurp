import logging
import os
import sys
from datetime import UTC, datetime, timedelta
from timeit import default_timer as timer

from fastapi import BackgroundTasks, FastAPI, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import UUID5, HttpUrl
from pymongo import DESCENDING, MongoClient
from pymongo.mongo_client import MongoClient as MongoClientType
from single_source import get_version

from guid_slurp.mongo import check_connection
from guid_slurp.database_sync import (
    MONGODB_COLLECTION,
    MONGODB_DATABASE,
    MONGODB_DUPLICATES,
    startup_import,
)

MONGODB_CONNECTION = os.getenv("MONGODB_CONNECTION", "mongodb://localhost:27017/")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(module)-14s %(lineno) 5d : %(message)s",
    stream=sys.stdout,
)
logging.getLogger("uvicorn.error").setLevel(logging.CRITICAL)


__version__ = get_version(__name__, "", default_return="0.0.1")
if __version__ is None:
    __version__ = "0.0.1"  # or some other default version

app = FastAPI(
    title="Guid Slurp API",
    description="API for resolving Podcasting 2.0 GUIDs and RSS feed URLs.",
    version=__version__,
    debug=False,
    # terms_of_service="http://example.com/terms/",
    # contact={
    #     "name": "Brian of London",
    #     "url": "https://guid.podping.org",
    # },
    # license_info={"name": "MIT", "url": ""},
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_cache_headers(max_age: int = 3600, reason: str = "") -> dict:
    """
    Returns the cache headers for Cloudflare
    """
    headers = {}
    headers[
        "Cache-Control"
    ] = f"public, max-age={max_age}, stale-while-revalidate=86400"
    headers["Expires"] = (datetime.now(tz=UTC) + timedelta(seconds=max_age)).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )
    headers["Pragma"] = "cache"
    headers["X-Reason"] = reason if reason else ""
    headers["Last-Modified"] = datetime.now(tz=UTC).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )
    return headers


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = timer()
    logging.info(f"MongoDB connection: {MONGODB_CONNECTION}")
    headers = request.headers
    response = await call_next(request)
    process_time = timer() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    if not request.url.path == "/info/":
        logging.info(
            f"{headers.get('cf-ipcountry')} IP: {headers.get('cf-connecting-ip')} "
            f"Referer: {headers.get('referer')} "
            f"Request: {request.url.path} query: {request.url.query} "
            f"time: {process_time*1000:.3f}ms"
        )
    # new_headers = get_cache_headers(max_age=3600, reason="API")
    # # combine response.headers with the new_headers
    # response.headers.update(new_headers)

    logging.debug(f"Process time: {process_time}")
    return response


def is_running_in_docker() -> bool:
    return os.path.exists("/.dockerenv")


@app.on_event("startup")
async def startup_event() -> None:
    """Startup code"""
    global MONGODB_CONNECTION
    logging.info(f"Logger Starting Guid Slurp API {__name__}")
    logging.info(f"MongoDB connection: {MONGODB_CONNECTION}")
    if is_running_in_docker():
        logging.info("Running in Docker")
        MONGODB_CONNECTION = "mongodb://mongodb-gs:27017/"
    logging.info(f"MongoDB connection check: {check_connection(MONGODB_CONNECTION)}")
    logging.info(f"MongoDB connection: {MONGODB_CONNECTION}")


@app.get("/", tags=["resolver"])
async def root(guid: UUID5 | str = "", url: HttpUrl | str = ""):
    """
    Resolve a GUID or URL to a RSS feed URL. Will always
    resolve a GUID first if both are passed.
    """
    if guid:
        return await resolve_guid(guid)
    if url:
        return await resolve_url(url)

    raise HTTPException(status_code=404, detail="Item not found")


def check_database_fileinfo() -> dict | None:
    logging.info(f"MongoDB connection: {MONGODB_CONNECTION}")
    with MongoClient(MONGODB_CONNECTION) as client:  # type: MongoClientType
        db = client[MONGODB_DATABASE]
        latest_record = db["fileInfo"].find_one(sort=[("timestamp", DESCENDING)])
    return latest_record


@app.get("/info/", tags=["info"])
async def info():
    """
    Returns information about the API and checks that it is working
    """
    try:
        file_info = check_database_fileinfo()
        # delete the _id field
        del file_info["_id"]
    except Exception as e:
        file_info = {"error": str(e)}
    return {
        "message": "Guid Slurp API",
        "version": __version__,
        "status": "OK",
        "time": datetime.now(tz=UTC).isoformat(),
        "file_info": file_info,
    }


@app.get("/guid/{guid}", tags=["resolver"])
async def resolve_guid(guid: UUID5 | str):
    """
    Resolve a GUID to a RSS feed URL.
    """
    logging.info(f"MongoDB connection: {MONGODB_CONNECTION}")
    with MongoClient(MONGODB_CONNECTION) as client:  # type: MongoClientType
        collection = client[MONGODB_DATABASE][MONGODB_COLLECTION]
        cursor = collection.find({"podcastGuid": str(guid)}, {"_id": 0})
        results = [doc for doc in cursor]
    if results:
        return results
    raise HTTPException(status_code=404, detail="Item not found")


@app.get("/url/", tags=["resolver"])
async def resolve_url(url: HttpUrl):
    """
    Resolve a RSS feed URL to a GUID.
    """
    logging.info(f"MongoDB connection: {MONGODB_CONNECTION}")
    with MongoClient(MONGODB_CONNECTION) as client:  # type: MongoClientType
        collection = client[MONGODB_DATABASE][MONGODB_COLLECTION]
        cursor = collection.find({"url": url}, {"_id": 0})
        results = [doc for doc in cursor]
    if results:
        return results
    raise HTTPException(status_code=404, detail="Item not found")


@app.get("/itunesId/{itunesId}", tags=["resolver"])
async def resolve_itunesId(
    itunesId: int = Path(gt=0, le=100000000000, description="iTunes ID")
):
    """
    Resolve an iTunes ID to a RSS feed URL.
    """
    logging.info(f"MongoDB connection: {MONGODB_CONNECTION}")
    with MongoClient(MONGODB_CONNECTION) as client:  # type: MongoClientType
        collection = client[MONGODB_DATABASE][MONGODB_COLLECTION]
        cursor = collection.find({"itunesId": itunesId}, {"_id": 0})
        results = [doc for doc in cursor]
    if results:
        return results
    raise HTTPException(status_code=404, detail="Item not found")


@app.get("/podcastIndexId/{podcastIndexId}", tags=["resolver"])
async def resolve_podcastIndexId(podcastIndexId: int = Path(gt=0, le=100000000000)):
    """
    Resolve a PodcastIndex ID to a RSS feed URL.
    """
    logging.info(f"MongoDB connection: {MONGODB_CONNECTION}")
    with MongoClient(MONGODB_CONNECTION) as client:  # type: MongoClientType
        collection = client[MONGODB_DATABASE][MONGODB_COLLECTION]
        cursor = collection.find({"podcastIndexId": podcastIndexId}, {"_id": 0})
        results = [doc for doc in cursor]
    if results:
        return results
    raise HTTPException(status_code=404, detail="Item not found")


@app.get("/admin", tags=["admin"], include_in_schema=True)
async def admin(request: Request, background_tasks: BackgroundTasks):
    """
    Admin page lists when the raw data was imported
    """
    if request.headers.get("X-secret") == os.getenv("ADMIN_HEADER_SECRET"):
        with MongoClient(MONGODB_CONNECTION) as client:  # type: MongoClientType
            collection = client[MONGODB_DATABASE]["fileInfo"]
            cursor = collection.find({}, {"_id": 0}).sort("timestamp", -1)
            results = [doc for doc in cursor]
            return results

    return {"message": "not authorized"}


@app.get("/duplicates/", tags=["problems"], include_in_schema=True)
async def duplicates(guid: str = Query("", description="GUID")):
    """
    Find duplicate GUIDs. Returns a static dump of all duplicated IDs.
    If no GUID is passed, it will return all duplicates.
    """
    if guid:
        query = {"_id": str(guid)}
    else:
        query = {}
    logging.info(f"MongoDB connection: {MONGODB_CONNECTION}")
    with MongoClient(MONGODB_CONNECTION) as client:  # type: MongoClientType
        collection = client[MONGODB_DATABASE][MONGODB_DUPLICATES]
        cursor = collection.find(query)
        results = []
        for doc in cursor:
            doc["podcastGuid"] = doc["_id"]
            # delete the doc["_id"] key
            del doc["_id"]
            results.append(doc)
        # results = [doc for doc in cursor]

    if results:
        return results
    raise HTTPException(status_code=404, detail="Item not found")
