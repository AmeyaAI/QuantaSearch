import os
import time
import uuid
import asyncio
from requests.utils import unquote
from contextlib import asynccontextmanager

from fastapi import HTTPException, APIRouter

from db.db import db
import core.file_searcher as rt
from logger.api_logger import logger
from event_driven.producer import add_queue, add_delete_queue
from utils.util import get_file_status, get_insertable_data, _stream_response

from schemas.schema import (
    DeleteFile,
    Filelister,
    PreviewBody,
    DraftUpload,
    QueryRequest,
    PublishUpload,
    VersionChange,
)

MAX_CONCURRENT_TASKS = 1

@asynccontextmanager
async def lifespan(app: APIRouter):
    
    for _ in range(MAX_CONCURRENT_TASKS):
        asyncio.create_task(worker())
        
    yield
    
    shutdown_event.set()
    await task_queue.join()


m_router = APIRouter(lifespan=lifespan)


task_queue = asyncio.Queue()
shutdown_event = asyncio.Event()
results: dict[int, asyncio.Future] = {}


get_list = rt.Filelist(timeout=36000, num_concurrent_runs=2)
updater = rt.MetaUpdater(timeout=36000, num_concurrent_runs=2)
searcher = rt.FileSearcher(timeout=36000, num_concurrent_runs=2)


async def worker():
    """Worker that processes tasks from the queue"""
    while not shutdown_event.is_set():
        try:
            eid, func, kvargs = await asyncio.wait_for(task_queue.get(), timeout=5)
            
            ret, result = await func.run(**kvargs)
            
            if eid in results:
                results[eid].set_result((ret, result))
                
            task_queue.task_done()
        except asyncio.TimeoutError:
            continue




@m_router.post("/user/upload_draft", tags=["USER-END"])
async def draft_upload(draft_body: DraftUpload):
    
    """Handles the draft file upload process for doc search.

    Args:
    
        - document_download_url (str | list): The pre-signed url of the file from s3.\n
        - user_id (str): It is the unique identifier for an individual user within the system.\n
        - realm (dict): It is the field which has a dynamic key-value pairs.\n
        - document_id (str | list): A unique identifier for each document.\n
        - uploaded_date (str | int): The uploaded date of the document. It can be a date string or timestamp.\n
    
    Returns:
    
        - dict: upload draft response containing:

                - event_id (str): Unique identifier for the search.\n
                - event_status (str): The status of the event.\n
                - message (str): The message for the event.\n
    
    Body Example:
    
        - document_download_url: "S3 url here"                  # S3 presigned URL.\n
        - document_id: "13cf3f31-b90f-4e91-ac0d-9777d322b46a"   # unique id for the file.\n
        - realm: {"client_id":"...", ...}                       # multiple key-value pairs for seperating documents.\n
        - uploaded_date: "2025-01-06 16:01:65"                  # Uploaded date for the document. It can be either str or int (timstamp).\n
        - user_id: "105573624549241064986"                      # Unique id for the user.\n
    
    Status codes:
    
        - 200: Successfull.\n
        - 400: Bad Request.\n
        - 405: Method not Allowed.\n
        - 406: Not Acceptable.\n
        - 415: Unsupported File Type.\n
        - 500: Internal server error.
    """
    try:
        st = time.perf_counter()
        
        status_code = 200
        error = None

        logger.info("Started draft Upload api event.......")

        uid = draft_body.user_id
        eid = str(uuid.uuid4())
        r_keys = list(draft_body.realm.keys())
        
        download_urls = [draft_body.document_download_url] if isinstance(draft_body.document_download_url, str) else draft_body.document_download_url
        documents_ids = [draft_body.document_id] if isinstance(draft_body.document_id, str) else draft_body.document_id
        file_names = [unquote(os.path.split(i.split("?")[0])[-1]) for i in download_urls]

        logger.debug(f"UID for the call uid : {uid}.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:

        for i, j, k in zip(file_names, documents_ids, download_urls):
            
            await add_queue(job={
                "uid":uid,
                "realm" : draft_body.realm,
                "user_id" : draft_body.user_id,
                "s3_file_path" : [k],
                "version_id" : 0,
                "document_ids" : [j],
                "uploaded_date" : draft_body.uploaded_date,
                "state" : "Draft",
                "extraction_mode" : draft_body._extarction_mode, 
                "parse_type": draft_body._parser_type,
                "file_names": [i],
                "event_id": eid,
                "route_key":"doc_search_files.process"

            })
            
            dat = await db.user_collection.find_one({"uid": uid, "realm": draft_body.realm}, {"_id":1, "files":1})
            ins_point = await get_insertable_data(uid, draft_body.realm)
            doc_count_data = await db.user_collection.find_one({"uid":uid})
            doc_count_data = doc_count_data if doc_count_data else {}
            total_vdocs = await db.vector_store.count_documents({"metadata.uid": uid}) if "total_vdocs" not in doc_count_data else doc_count_data["total_vdocs"]
            
            if dat and ins_point:
                keys = dat["files"].keys()
                
                if j in keys and dat["_id"] == ins_point["_id"]:
                    await db.user_collection.update_one({"_id": ins_point["_id"]},
                                                        {"$set": {f"files.{j}.status": "Processing"}})
            
                else:
                    await db.user_collection.update_one({"_id": ins_point["_id"]},
                                                        {"$set": {f"files.{j}": {"current_version": None,
                                                                                 "versions": [],
                                                                                 "status":"Processing",
                                                                                 "file_name" : i,
                                                                                 "uploaded_date": draft_body.uploaded_date,
                                                                                 "published_date": None,
                                                                                 "version_change_date": None}}})
            
            else:
                await db.user_collection.insert_one({"uid": uid, "r_keys" : r_keys, "realm": draft_body.realm,
                                                     "total_vdocs": total_vdocs,
                                                     "files": {j: {"current_version": None,
                                                                   "versions": [],
                                                                   "status":"Processing",
                                                                   "file_name" : i,
                                                                   "uploaded_date": draft_body.uploaded_date,
                                                                   "published_date": None,
                                                                   "version_change_date": None}}})
                
        ed = time.perf_counter()
        logger.info(f"Time taken to complete the Draft upload api : {ed-st} seconds.")

        return {"message":"Upload Successfull", "event_id": eid,
                "file_event_ids": documents_ids, "event_status": "Processing"}
            
    except Exception as e:
        
        if isinstance(e, HTTPException):
            error = e.detail
            status_code = e.status_code
            logger.error(f"Error: {error}")

            for i, j in zip(file_names, documents_ids):
                db_dat = await db.user_collection.find_one({"uid":uid, "realm":draft_body.realm}, {"_id":1, "files":1})
                ins_point = await get_insertable_data(uid, draft_body.realm)
                doc_count_data = await db.user_collection.find_one({"uid":uid})
                doc_count_data = doc_count_data if doc_count_data else {}
                total_vdocs = await db.vector_store.count_documents({"metadata.uid": uid}) if "total_vdocs" not in doc_count_data else doc_count_data["total_vdocs"]
                
                if db_dat and ins_point:
                    keys = db_dat["files"].keys()
                    
                    if j in keys and dat["_id"] == ins_point["_id"]:
                        await db.user_collection.update_one({"_id": ins_point["_id"]},
                                                            {"$set": {f"files.{j}.status": "Failed"}})
                
                    else:
                        await db.user_collection.update_one({"_id": ins_point["_id"]},
                                                            {"$set": {f"files.{j}": {"current_version": None,
                                                                                    "versions": [],
                                                                                    "status":"Failed",
                                                                                    "file_name" : i,
                                                                                    "uploaded_date": draft_body.uploaded_date,
                                                                                    "published_date": None,
                                                                                    "version_change_date": None}}})
                
                else:
                    await db.user_collection.insert_one({"uid": uid, "r_keys" : r_keys, "realm": draft_body.realm,
                                                         "total_vdocs": total_vdocs,
                                                         "files": {j: {"current_version": None,
                                                                       "versions": [],
                                                                       "status":"Failed",
                                                                       "file_name" : i,
                                                                       "uploaded_date": draft_body.uploaded_date,
                                                                       "published_date": None,
                                                                       "version_change_date": None}}})
            
            raise HTTPException(status_code=status_code, detail=error)
        
        else:
            error = str(e)
            status_code = 500
            logger.error(f"Error: {e.__class__.__name__} : {str(e)}")
            
            for i, j in zip(file_names, documents_ids):
                db_dat = await db.user_collection.find_one({"uid":uid, "realm":draft_body.realm}, {"_id":1, "files":1})
                ins_point = await get_insertable_data(uid, draft_body.realm)
                doc_count_data = await db.user_collection.find_one({"uid":uid})
                doc_count_data = doc_count_data if doc_count_data else {}
                total_vdocs = await db.vector_store.count_documents({"metadata.uid": uid}) if "total_vdocs" not in doc_count_data else doc_count_data["total_vdocs"]
            
                if db_dat and ins_point:
                    keys = db_dat["files"].keys()
                    
                    if j in keys and dat["_id"] == ins_point["_id"]:
                        await db.user_collection.update_one({"_id": ins_point["_id"]},
                                                            {"$set": {f"files.{j}.status": "Failed"}})
                
                    else:
                        await db.user_collection.update_one({"_id": ins_point["_id"]},
                                                            {"$set": {f"files.{j}": {"current_version": None,
                                                                                    "versions": [],
                                                                                    "status":"Failed",
                                                                                    "file_name" : i,
                                                                                    "uploaded_date": draft_body.uploaded_date,
                                                                                    "published_date": None,
                                                                                    "version_change_date": None}}})
                
                else:
                    await db.user_collection.insert_one({"uid": uid, "r_keys" : r_keys, "realm": draft_body.realm,
                                                         "total_vdocs": total_vdocs,
                                                         "files": {j: {"current_version": None,
                                                                       "versions": [],
                                                                       "status":"Failed",
                                                                       "file_name" : i,
                                                                       "uploaded_date": draft_body.uploaded_date,
                                                                       "published_date": None,
                                                                       "version_change_date": None}}})
            
            raise HTTPException(status_code=500, detail=str(e))


@m_router.post("/user/upload_publish", tags=["USER-END"])
async def publish_upload(publish_body: PublishUpload):
     
    """Handles the publish file upload process for doc search.

    Args:
    
        - document_download_url (str | list): The pre-signed url of the file from s3.\n
        - user_id (str): It is the unique identifier for an individual user within the system.\n
        - realm (dict): It is the field which has a dynamic key-value pairs.\n
        - document_id (str | list): A unique identifier for each document.\n
        - version_id (str | int): The version id of the document. It must not be 0.\n
        - published_date (str | int): The published date of the document. It can be a date string or timestamp.\n
    
    Returns:
    
        - dict: upload publish response containing:

                - event_id (str): Unique identifier for the search.\n
                - event_status (str): The status of the event.\n
                - message (str): The message for the event.\n
    
    Body Example:
    
        - document_download_url: "S3 presigned url here"        # S3 presigned URL.\n
        - document_id: "13cf3f31-b90f-4e91-ac0d-9777d322b46a"   # unique id for the file.\n
        - realm: {"client_id":"...", ...}                       # multiple key-value pairs for seperating documents.\n
        - published_date: "2025-01-06 16:01:65"                 # published date of the document. It can be either str or int (timstamp).\n
        - user_id: "105573624549241064986"                      # Unique id for the user.\n
        - version_id: 1                                         # It mube an integer indicating the version of the file.\n
    
    Status codes:
    
        - 200: Successfull.\n
        - 400: Bad Request.\n
        - 405: Method not Allowed.\n
        - 406: Not Acceptable.\n
        - 415: Unsupported File Type.\n
        - 500: Internal server error.
    """ 
    try:
        st = time.perf_counter()
        
        status_code = 200
        error = None
        
        logger.info("Started publish Upload api event.......")
        
        uid = publish_body.user_id
        eid = str(uuid.uuid4())
        r_keys = list(publish_body.realm.keys())
        
        download_urls = [publish_body.document_download_url] if isinstance(publish_body.document_download_url, str) else publish_body.document_download_url
        documents_ids = [publish_body.document_id] if isinstance(publish_body.document_id, str) else publish_body.document_id
        file_names = [unquote(os.path.split(i.split("?")[0])[-1]) for i in download_urls]
        
        logger.debug(f"UID for the call uid : {uid}.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
   
    try:
        
        for i, j, k in zip(file_names, documents_ids, download_urls):
            
            await add_queue(job={
                "uid":uid,
                "realm" : publish_body.realm,
                "user_id" : publish_body.user_id,
                "s3_file_path" : [k],
                "version_id" : publish_body.version_id,
                "document_ids" : [j],
                "published_date" : publish_body.published_date,
                "state" : "Publish",
                "extraction_mode" : publish_body._extarction_mode, 
                "parse_type": publish_body._parser_type,
                "event_id": eid,
                "file_names": [i],
                "route_key":"doc_search_files.process"
            })
            
            dat = await db.user_collection.find_one({"uid": uid, "realm": publish_body.realm}, {"_id":1, "files":1})
            ins_point = await get_insertable_data(uid, publish_body.realm)
            doc_count_data = await db.user_collection.find_one({"uid":uid})
            doc_count_data = doc_count_data if doc_count_data else {}
            total_vdocs = await db.vector_store.count_documents({"metadata.uid": uid}) if "total_vdocs" not in doc_count_data else doc_count_data["total_vdocs"]

            if dat and ins_point:
                keys = dat["files"].keys()
                
                if j in keys and dat["_id"] == ins_point["_id"]:
                    await db.user_collection.update_one({"_id": ins_point["_id"]},
                                                        {"$set": {f"files.{j}.status":"Processing"}})
            
                else:
                    await db.user_collection.update_one({"_id": ins_point["_id"]},
                                                        {"$set" : {f"files.{j}" : {"current_version": None,
                                                                                   "versions": [],
                                                                                   "status":"Processing",
                                                                                   "file_name" : i,
                                                                                   "uploaded_date": publish_body.published_date,
                                                                                   "published_date": publish_body.published_date,
                                                                                   "version_change_date": None}}})
             
            else:
                await db.user_collection.insert_one({"uid": uid, "r_keys" : r_keys, "realm": publish_body.realm,
                                                    "total_vdocs": total_vdocs,
                                                    "files": {j: {"current_version": None,
                                                                "versions": [],
                                                                "status":"Processing",
                                                                "file_name" : i,
                                                                "uploaded_date": publish_body.published_date,
                                                                "published_date": publish_body.published_date,
                                                                "version_change_date": None}}})
        
        ed = time.perf_counter()
        logger.info(f"Time taken to complete the Publish upload api : {ed-st} seconds.")

        return {"message":"Upload Successfull", "event_id": eid, 
                "file_event_ids": documents_ids, "event_status": "Processing"}
       
    except Exception as e:
        
        if isinstance(e, HTTPException):
            error = e.detail
            status_code = e.status_code
            logger.error(f"Error: {error}")
            
            for i, j in zip(file_names, documents_ids):
                db_dat = await db.user_collection.find_one({"uid":uid, "realm":publish_body.realm}, {"_id":1, "files":1})
                ins_point = await get_insertable_data(uid, publish_body.realm)
                doc_count_data = await db.user_collection.find_one({"uid":uid})
                doc_count_data = doc_count_data if doc_count_data else {}
                total_vdocs = await db.vector_store.count_documents({"metadata.uid": uid}) if "total_vdocs" not in doc_count_data else doc_count_data["total_vdocs"]

                if db_dat and ins_point:
                    keys = db_dat["files"].keys()
                    
                    if j in keys and dat["_id"] == ins_point["_id"]:
                        await db.user_collection.update_one({"_id": ins_point["_id"]},
                                                            {"$set": {f"files.{j}.status": "Failed"}})
                
                    else:
                        await db.user_collection.update_one({"_id": ins_point["_id"]},
                                                            {"$set": {f"files.{j}": {"current_version": None,
                                                                          "versions": [],
                                                                          "status":"Failed",
                                                                          "file_name" : i,
                                                                          "uploaded_date": publish_body.published_date,
                                                                          "published_date": publish_body.published_date,
                                                                          "version_change_date": None}}})
                    
                else:
                    await db.user_collection.insert_one({"uid": uid, "r_keys" : r_keys, "realm": publish_body.realm,
                                                        "total_vdocs": total_vdocs,
                                                        "files": {j: {"current_version": None,
                                                                      "versions": [],
                                                                      "status":"Failed",
                                                                      "file_name" : i,
                                                                      "uploaded_date": publish_body.published_date,
                                                                      "published_date": publish_body.published_date,
                                                                      "version_change_date": None}}})
            
            raise HTTPException(status_code=status_code, detail=error)
        
        else:
            error = str(e)
            status_code = 500
            logger.error(f"Error: {e.__class__.__name__} : {str(e)}")
            
            for i, j in zip(file_names, documents_ids):
                db_dat = await db.user_collection.find_one({"uid":uid, "realm":publish_body.realm}, {"_id":1, "files":1})
                ins_point = await get_insertable_data(uid, publish_body.realm)
                doc_count_data = await db.user_collection.find_one({"uid":uid})
                doc_count_data = doc_count_data if doc_count_data else {}
                total_vdocs = await db.vector_store.count_documents({"metadata.uid": uid}) if "total_vdocs" not in doc_count_data else doc_count_data["total_vdocs"]

                if db_dat and ins_point:
                    keys = db_dat["files"].keys()
                    
                    if j in keys and dat["_id"] == ins_point["_id"]:
                        await db.user_collection.update_one({"_id": ins_point["_id"]},
                                                            {"$set": {f"files.{j}.status": "Failed"}})
                
                    else:
                        await db.user_collection.update_one({"_id": ins_point["_id"]},
                                                            {"$set": {f"files.{j}": {"current_version": None,
                                                                          "versions": [],
                                                                          "status":"Failed",
                                                                          "file_name" : i,
                                                                          "uploaded_date": publish_body.published_date,
                                                                          "published_date": publish_body.published_date,
                                                                          "version_change_date": None}}})
                
                else:
                    await db.user_collection.insert_one({"uid": uid, "r_keys" : r_keys, "realm": publish_body.realm,
                                                         "total_vdocs": total_vdocs,
                                                         "files": {j: {"current_version": None,
                                                                       "versions": [],
                                                                       "status":"Failed",
                                                                       "file_name" : i,
                                                                       "uploaded_date": publish_body.published_date,
                                                                       "published_date": publish_body.published_date,
                                                                       "version_change_date": None}}})
            
            raise HTTPException(status_code=500, detail=str(e))
        
        
        
@m_router.get("/user/file_upload_status_check", tags=["USER-END"])
async def status_check(user_id:str, document_id:str):
    "Returns the status of the document using the document id"
    
    """Returns the status of the document using the document id
    
    Args:
    
        - user_id (str): It is the unique identifier for an individual user within the system.\n
        - document_id (str): A unique identifier for the document.\n

    Raises:
        - 200: Successfull.\n
        - 500: Internal server error.

    Returns:
        - dict: status check response containing:

            - status (str): Success | Processing | Failed.\n
    """
    
    
    try:
        
        status_code = 200
        error = None

        logger.info("Started file status check api event.......")

        uid = user_id
                
        logger.debug(f"UID for the call uid : {uid}.")
        logger.debug(f"Call with Document id : {document_id}.")
        
        return {"status" : await get_file_status(uid, document_id)}
    
    except Exception as e:
        
        if isinstance(e, HTTPException):
            error = e.detail
            status_code = e.status_code
            logger.error(f"Error: {error}")
            
            raise HTTPException(status_code=status_code, detail=error)
            
        else:
            error = str(e)
            status_code = 500
            logger.error(f"Error: {e.__class__.__name__} : {str(e)}")
            
            raise HTTPException(status_code=status_code, detail=error)
        


@m_router.post("/user/revert_published_version", tags=["USER-END"])
async def version_change(verch_body: VersionChange):
    
    """Handles the version change process for the document in doc search. It only changes the latest version of the published documents only.

    Args:

        - realm (dict): It is the field which has a dynamic key-value pairs.\n
        - document_id (str): A unique identifier for each document.\n
        - user_id (str): It is the unique identifier for an individual user within the system.\n
        - marked_latest_version (str | int): The version to mark as latest.\n
        - version_change_date (str | int): The version change date of the document. It can be a date string or timestamp.\n
    
    Returns:
    
        - dict: version change response containing:

                - event_id (str): Unique identifier for the search.\n
                - event_status (str): The status of the event.\n
                - message (str): The message for the event.\n
    
    Status codes:
    
        - 200: Successfull.\n
        - 405: Method not Allowed.\n
        - 406: Not Acceptable.\n
        - 500: Internal server error.
    """
 
    try:
        status_code = 200
        error = None

        logger.info("Started version change api event.......")

        uid = verch_body.user_id
        eid = str(uuid.uuid4())

        logger.debug(f"UID for the call uid : {uid}.")

        st = time.time()
        ret, result = await updater.run(
            uid = uid,
            realm = verch_body.realm,
            document_id = verch_body.document_id,
            latest_version = verch_body.marked_latest_version,
            version_change_date = verch_body.version_change_date,
            state = "Publish"
        )
        ed = time.time()

        if ret:
            logger.debug("Successfully completed version change event run.")
            logger.info(f"time-taken to run the version change : {ed - st} seconds.")
            return {"message":result, "event_id": eid, "event_status": "success"}
        
        elif not ret and result == "AssertionError :- realm attributes does not match or no data to process.":
            raise HTTPException(status_code=406, detail=result)
        
        else:
            raise HTTPException(status_code=500, detail=result)
        
    except Exception as e:
        if isinstance(e, HTTPException):
            error = e.detail
            status_code = e.status_code
            logger.error(f"Error: {error}")
            raise HTTPException(status_code=status_code, detail=error)
        
        else:
            error = str(e)
            status_code = 500
            logger.error(f"Error: {e.__class__.__name__} : {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        


@m_router.post("/user/archive_document", tags=["USER-END"])
async def archive_file(del_body: DeleteFile):
    
    """Handles the file deleting process for files in doc search.

    Args:
    
        - realm (dict): It is the field which has a dynamic key-value pairs.\n
        - document_id (str): A unique identifier for each document.\n
        - user_id (str): It is the unique identifier for an individual user within the system.\n
        - version_id (str | int | None): The version id of the document to archive. If 'None' is given it will delete all files which matched the document id.\n
        - state (str): The state of the document which is either 'Draft' or 'Publish'.\n
    
    Returns:
    
        - dict: Archive file response containing:

                - event_id (str): Unique identifier for the search.\n
                - event_status (str): The status of the event.\n
                - message (str): The message for the event.\n
    
    Status codes:
    
        - 200: Successfull.\n
        - 405: Method not Allowed.\n
        - 406: Not Acceptable.\n
        - 500: Internal server error.
    """
    
    try:
        st = time.perf_counter()
        
        status_code = 200
        error = None

        logger.info("Started delete file api event.......")

        uid = del_body.user_id
        eid = str(uuid.uuid4())

        logger.debug(f"UID for the call uid : {uid}.")

        st = time.time()
        reply = await add_delete_queue(
            job_data={
                "uid":uid,
                "realm":del_body.realm,
                "document_id":del_body.document_id,
                "version_id": del_body.version_id,
                "state": del_body.state,
                "route_key": "doc_search_delete.process"
            }
            )
        
        ret = False
        async for response in _stream_response(reply["correlation_id"], reply["reply_queue_name"]):
            out = response
            print(f"Streaming response: {out}")
            
            if out["type"] == "error":
                ret = False
            
            elif out["data"]["done"]:
                ret = True
        
        ed = time.time()

        if ret:
            logger.debug("Successfully completed delete file event run.")
            logger.info(f"time-taken to run the delete file : {ed - st} seconds.")
            return {"message":out["data"]["msg"], "event_id": eid, "event_status": "success"}
        
        elif not ret and out["data"]["msg"] == "AssertionError :- realm attributes does not match or no data to process.":
            raise HTTPException(status_code=406, detail=out["data"]["msg"])
        
        else:
            raise HTTPException(status_code=500, detail=out["data"]["msg"])
        
    except Exception as e:
        
        if isinstance(e, HTTPException):
            error = e.detail
            status_code = e.status_code
            logger.error(f"Error: {error}")
            raise HTTPException(status_code=status_code, detail=error)
        
        else:
            error = str(e)
            status_code = 500
            logger.error(f"Error: {e.__class__.__name__} : {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))



@m_router.post("/platform/list_files", tags=["Platform"])
async def get_file_list(user_body: Filelister):
    
    """Returns the uploaded files for a specific user doc search.

    Args:\n
        - realm (dict): It is the field which has a dynamic key-value pairs.\n
        - user_id (str): It is the unique identifier for an individual user within the system.\n
        
    Returns:
    
        - dict: Get user files response containing:

                - event_id (str): Unique identifier for the search.\n
                - event_status (str): The status of the event.\n
                - message (str): The message for the event.\n
                - result (List[dict]): The result containing the fetched data:
                
                        - file_name (str): The name of the document.\n
                        - uploaded_date (str | int | None): The published date of the document in date string or timestamp.\n
                        - published_date (str | int | None): The published date of the document in date string or timestamp.\n
                        - version_change_date (str | int | None): The published date of the document in date string or timestamp.\n
                        - document_id (str): A unique identifier for the document.\n
                        - versions (List[str | int]): List of available versions for the document.\n 
                        - current_version (int): The current version of the document.\n
        
    Status codes:
    
        - 200: Successfull.\n
        - 406: Not Acceptable.\n
        - 500: Internal server error.
    """
    
    try:
        st = time.perf_counter()
        
        status_code = 200
        error = None

        logger.info("Started get files api event.......")

        uid = user_body.user_id
        eid = str(uuid.uuid4())

        logger.debug(f"UID for the call uid : {uid}.")

        st = time.time()
        ret, result = await get_list.run(
            uid = uid, realm=user_body.realm
        )
        ed = time.time()

        if ret:
            logger.debug("Successfully completed get files event run.")
            logger.info(f"time-taken to run the get_file_list : {ed - st} seconds.")
            return {"event_id": eid, "event_status": "success", "message": "Successfully fetched user file data.",
                    "result": result}
        
        elif not ret and result == "AssertionError :- realm attributes does not match or no data to process.":
            raise HTTPException(status_code=406, detail=result)
        
        else:
            raise HTTPException(status_code=500, detail=result)
        
    except Exception as e:
        
        if isinstance(e, HTTPException):
            error = e.detail
            status_code = e.status_code
            logger.error(f"Error: {error}")
            raise HTTPException(status_code=status_code, detail=error)
        
        else:
            error = str(e)
            status_code = 500
            logger.error(f"Error: {e.__class__.__name__} : {str(e)}")
            raise HTTPException(status_code=500, detail=result)



@m_router.post("/user/search", tags=["USER-END"])
async def query_documents(query_request: QueryRequest):
    
    """Handles the file documents search process in doc search for the latest documents only.

    Args:\n
        - query (str): The search query to retrieve the similar files.\n
        - realm (dict): It is the field which has a dynamic key-value pairs.\n
        - user_id (str): It is the unique identifier for an individual user within the system.\n
        - state (str): The state of the document which is either 'Draft' or 'Publish'. Default to 'Publish'.\n
        - exact_match (bool): It is a flag to support the partial and exact match when searching documents. Default to 'False'.\n
    
    Returns:
    
        - dict: Search response containing:

                - event_id (str): Unique identifier for the search.\n
                - event_status (str): The status of the event.\n
                - message (str): The message for the event.\n
                - result (List[dict]): The result containing the fetched data:

                        - realm (dict): It is the field which has a dynamic key-value pairs.\n
                        - user_id (str): It is the unique identifier for an individual user within the system.\n
                        - document_name (str): The name of the document.\n
                        - document_id (str): The unique id of the document.\n
                        - version_id (str | int): The version id of the document.\n 
                        - relavence_score (float): The relavance score of the document.\n
                        - uploaded_date (str | int | None): The published date of the document in date string or timestamp.\n
                        - published_date (str | int | None): The published date of the document in date string or timestamp.\n
                        - version_change_date (str | int | None): The published date of the document in date string or timestamp.\n

    
    Status codes:
    
        - 200: Successfull.\n
        - 405: Method not Allowed.\n
        - 406: Not Acceptable.\n
        - 500: Internal server error.
    """

    try:
        status_code = 200
        error = None

        logger.info("Started query api event.......")

        uid = query_request.user_id
        eid = str(uuid.uuid4())

        logger.debug(f"UID for the call uid : {uid}.")
        logger.debug(f"the user query is : {query_request.query}")
        
        st = time.time()
        ret, result = await searcher.run(
            uid = uid,
            realm = query_request.realm,
            query = query_request.query,
            state = query_request.state,
            exact_match = query_request.exact_match,
        )
        ed = time.time()

        if ret: 
            logger.debug("Successfully completed doc search event run.")
            logger.info(f"time-taken to run the search query : {ed - st} seconds.")
            return {"event_id": eid, "event_status": "success", "result":result, "message":"success"}
        
        else:
            raise HTTPException(status_code=500, detail=result)
    
    except Exception as e:
        
        if isinstance(e, HTTPException):
            error = e.detail
            status_code = e.status_code
            logger.error(f"Error: {error}")
            raise HTTPException(status_code=status_code, detail=error)
        
        else:
            error = str(e)
            status_code = 500
            logger.error(f"Error: {e.__class__.__name__} : {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    
        
        
@m_router.post("/user/search_preview", tags=["USER-END"])
async def search_preview(preview_body:PreviewBody):
    """Get the preview for the specific documents using the unique document id.

    Args:\n
        - query (str): The search query to retrieve the similar files.\n
        - realm (dict): It is the field which has a dynamic key-value pairs.\n
        - document_id (str): A unique identifier for each document.\n
        - user_id (str): It is the unique identifier for an individual user within the system.\n
        - state (str): The state of the document which is either 'Draft' or 'Publish'.\n
    
    Raises:
        - 200: Successfull.\n
        - 500: Internal server error.

    Returns:
        - dict: preview response containing:

            - preview (List(str)): The preview for the query keyword in the document.\n
    """
    
    try:
        st = time.perf_counter()
        
        status_code = 200
        error = None

        logger.info("Started file preview api event.......")

        uid = preview_body.user_id
        
        logger.debug(f"UID for the call uid : {uid}.")
        logger.debug(f"Call with Document id : {preview_body.document_id}.")
        
        st = time.time()
        previwer = rt.FileSearcherPreview(timeout=3600, num_concurrent_runs=2)
        ret, result = await previwer.run(
            uid = uid,
            realm = preview_body.realm,
            query = preview_body.query,
            state = preview_body.state,
            document_id = preview_body.document_id,
        )
        ed = time.time()

        if ret: 
            logger.debug("Successfully completed file preview event run.")
            logger.info(f"time-taken to run the file preview : {ed - st} seconds.")
            return {"preview": result["preview_texts"],
                    "preview_count": sum([len(i["previews"]) for i in result["preview_texts"]])}
        
        else:
            raise HTTPException(status_code=500, detail=result)
    
    except Exception as e:
        
        if isinstance(e, HTTPException):
            error = e.detail
            status_code = e.status_code
            logger.error(f"Error: {error}")
            raise HTTPException(status_code=status_code, detail=error)
        
        else:
            error = str(e)
            status_code = 500
            logger.error(f"Error: {e.__class__.__name__} : {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))