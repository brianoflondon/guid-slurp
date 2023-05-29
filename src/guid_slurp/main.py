import logging
import uuid
from timeit import default_timer as timer

import rfc3987
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pymongo.mongo_client import MongoClient as MongoClientType
from single_source import get_version

from guid_slurp.startup import MONGODB_COLLECTION, MONGODB_CONNECTION, MONGODB_DATABASE

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


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = timer()
    headers = request.headers
    response = await call_next(request)
    process_time = timer() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    logging.info(
        f"{headers.get('cf-ipcountry')} IP: {headers.get('cf-connecting-ip')} "
        f"Referer: {headers.get('referer')} "
        f"Request: {request.url.path} query: {request.url.query} "
        f"time: {process_time*1000:.3f}ms"
    )
    logging.debug(f"Process time: {process_time}")
    return response


def is_valid_uuid4(uuid_string: str) -> bool:
    try:
        _ = uuid.UUID(uuid_string, version=4)
        return True
    except ValueError:
        # If it's a value error, then the string is not a valid hex code for a UUID.
        return False


def is_valid_iri(iri):
    try:
        rfc3987.parse(iri, rule="IRI")
        return True
    except ValueError:
        return False


@app.get("/")
async def root(guid: str = "", url: str = ""):
    """
    Resolve a GUID or URL to a RSS feed URL. Will always
    resolve a GUID first if both are passed.
    """
    if guid:
        return await resolve_guid(guid)
    if url:
        return await resolve_url(url)

    raise HTTPException(status_code=404, detail="Item not found")


@app.get("/guid/{guid}")
async def resolve_guid(guid: str):
    """
    Resolve a GUID to a RSS feed URL.
    """
    if not is_valid_uuid4(guid):
        raise HTTPException(status_code=400, detail="Bad GUID")
    with MongoClient(MONGODB_CONNECTION) as client:  # type: MongoClientType
        collection = client[MONGODB_DATABASE][MONGODB_COLLECTION]
        cursor = collection.find({"podcastGuid": guid}, {"_id": 0})
        results = [doc for doc in cursor]
    if results:
        return results
    raise HTTPException(status_code=404, detail="Item not found")


@app.get("/url/")
async def resolve_url(url: str):
    """
    Resolve a RSS feed URL to a GUID.
    """
    if not is_valid_iri(url):
        raise HTTPException(status_code=400, detail="Bad RSS URL")
    with MongoClient(MONGODB_CONNECTION) as client:  # type: MongoClientType
        collection = client[MONGODB_DATABASE][MONGODB_COLLECTION]
        cursor = collection.find({"url": url}, {"_id": 0})
        results = [doc for doc in cursor]
    if results:
        return results
    raise HTTPException(status_code=404, detail="Item not found")
