import time
import uuid
import hashlib

from fastapi import HTTPException, APIRouter

from db.db import db
from logger.api_logger import logger
from utils.pipelines import load_document_count_pipeline, load_total_doc_count_pipeline


p_router = APIRouter(prefix="/platform", tags=["Platform"])


@p_router.get("/get_document_count_meta")
async def get_document_meta(user_id: str):
    
    try:
        st = time.perf_counter()
        
        logger.info("Started doc count api event.......")

        uid = user_id
        eid = str(uuid.uuid4())
        
        logger.debug(f"UID for the call uid : {uid}.")
        
        pipeline = await load_document_count_pipeline(uid)
        tc_pipeline = await load_total_doc_count_pipeline(uid)
        
        res = [i async for i in await db.user_collection.aggregate(pipeline)]
        tc_doc = [i async for i in await db.vector_store.aggregate(tc_pipeline)]
        
        tc_doc_count = tc_doc[0].get("uniqueFileNames", 0) if tc_doc else 0
        
        ed= time.time()
        
        logger.debug("Successfully completed document count event run.")
        logger.info(f"time-taken to run the document count : {ed - st} seconds.")
        
        return {"message":"success", "result":res, "total_doc_count":tc_doc_count, 
                "event_id": eid, "event_status": "success"}
        
        
    except Exception as e:
        error = str(e)
        status_code = 500
        logger.error(f"Error: {e.__class__.__name__} : {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))