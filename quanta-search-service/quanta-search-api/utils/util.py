# -----------------------------------------------------------------------------
# Copyright 2025 DPOD Labs Private Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# -----------------------------------------------------------------------------


<<<<<<< HEAD
=======
import re
>>>>>>> c1e0d3d (Added copyright text on each source files)
import math
import json
import asyncio
from typing import Any
from llama_index.core import Document
from pymongo.asynchronous.collection import AsyncCollection

from db.db import db
from utils.load_envs import env
from logger.api_logger import logger
from utils.pipelines import get_insertable_data_pipeline
from event_driven.producer import get_msg_from_reply_queue, delete_reply_queue


def add_metadata(doc:Document, ev:Any) -> Document:
    """
    Add comprehensive metadata to a Document object.
    
    Enriches document with system metadata including user info, version details,
    realm information, and processing state. Also prepends filename to document text.
    
    Args:
        doc (Document): The document object to enrich with metadata
        ev (Any): Event data containing user and document information
        
    Returns:
        Document: Document with added metadata and updated text content
    """
    
    metadatas = {"datasource_type" : 'File Source',
                 "datasource_status" : 'active',
                 "uid" : ev.uid,
                 "user_id": ev.user_id,
                 "version_id": ev.version_id,
                 "document_id": ev.file_meta[doc.metadata['file_name']]["document_id"],
                 "published_date": ev.file_meta[doc.metadata['file_name']]["published_date"],
                 "version_change_date": ev.version_change_date,
                 "uploaded_date": ev.file_meta[doc.metadata['file_name']]["uploaded_date"],
                 "state": ev.state,
                 "realm": ev.realm
                }

    keys = list(metadatas.keys())
    
    if "usage" in doc.metadata:
        doc.metadata.pop("usage")
        
    text = doc.text_resource.text if doc.text_resource.text else ""
    doc.text_resource.text = f"File Name : {doc.metadata['file_name']}\n\n\n{text}"
    
    doc.excluded_llm_metadata_keys.extend(keys)
    doc.excluded_embed_metadata_keys.extend(keys)
    doc.metadata.update(metadatas)
    
    return doc



async def get_doc_lt_version(collection:AsyncCollection, uid:str, realm:dict, doc_id:str) -> tuple[list, list]:
    """
    Retrieve current version and available versions for a document.
    
    Fetches version information from the user collection for version
    management and validation purposes.
    
    Args:
        collection (AsyncCollection): MongoDB collection reference
        uid (str): User identifier
        realm (dict): Realm filter parameters
        doc_id (str): Document identifier
        
    Returns:
        tuple[list, list]: (current_version, available_versions)
    """
     
    data = await collection.find_one({"uid": uid, "realm":realm, f"files.{doc_id}": {"$exists":True}})

    try:
        return data["files"][doc_id]["current_version"], data["files"][doc_id]["versions"]
        
    except Exception as e:
        return [], []
    

async def check_realm_keys(collection:AsyncCollection, uid:str, realm:dict, upload:bool) -> bool:
    """
    Validate realm keys against user's registered realm configuration.
    
    Checks if provided realm keys match the user's configured realm keys
    to ensure data consistency and access control.
    
    Args:
        collection (AsyncCollection): MongoDB collection reference
        uid (str): User identifier
        realm (dict): Realm parameters to validate
        upload (bool): Whether this is for upload operation
        
    Returns:
        bool: True if realm keys are valid, False otherwise
    """
    
    data = await collection.find_one({"uid":uid, "realm":realm})
    rlm_keys = list(realm.keys())
    
    if data is not None:
        return not bool(set(rlm_keys).symmetric_difference(data["r_keys"]))
    else:
        return upload


async def get_total_doc(uid:str) -> int:
    """
    Get the total number of vector documents for a user.
    
    Retrieves cached document count or returns 0 if not available.
    Used for scaling and performance optimization.
    
    Args:
        uid (str): User identifier
        
    Returns:
        int: Total number of vector documents
    """
    
    doc = await db.user_collection.find_one({"uid": uid})
    tc_doc = doc if doc else {}
    return tc_doc.get("total_vdocs", 0)


async def get_file_status(uid:str, document_id:str) -> str:
    """
    Get the processing status of a specific document.
    
    Retrieves current status (Processing, Success, Failed, etc.)
    from user collection for status tracking.
    
    Args:
        uid (str): User identifier
        document_id (str): Document identifier
        
    Returns:
        str: Current status of the document or "Not Found"
    """
    
    res = await db.user_collection.find_one({"uid": uid, f"files.{document_id}": {"$exists":True}}, {"files":1})
    return res["files"][document_id].get("status", "Not Found")


def compute_score(doc_count, estimated_max=1000, base_score=0.7) -> float:
    """
    Compute relevance score using logarithmic scaling.
    
    Calculates document relevance scores using logarithmic distribution
    to handle varying document collection sizes fairly.
    
    Args:
        doc_count (int): Number of matching documents
        estimated_max (int, optional): Estimated maximum documents. Defaults to 1000
        base_score (float, optional): Base relevance score. Defaults to 0.7
        
    Returns:
        float: Computed relevance score capped at 0.9995
        
    Raises:
        ValueError: If doc_count is negative
    """
    
    if doc_count < 0:
        raise ValueError("doc_count must be non-negative")

    log_count = math.log(1 + doc_count)
    log_max = math.log(1 + estimated_max)
    scale = log_count / log_max
    rank = base_score + (1 - base_score) * scale
    return min(rank, 0.9995)


def compute_preview_score(relevance_score:float, preview_length:int) -> float:
    """
    Enhance relevance scores based on preview snippet availability.
    
    Adjusts document scores upward when quality preview snippets
    are available, improving ranking for documents with good context.
    
    Args:
        relevance_score (float): Original relevance score
        preview_length (int): Number of preview snippets available
        
    Returns:
        float: Enhanced relevance score capped at MAX_SCORE
    """
    
    if relevance_score < env.BASE_PREVIEW_SCORE and preview_length > 0:
        relevance_score = env.BASE_PREVIEW_SCORE
        abs_diff = abs(env.MAX_SCORE - relevance_score)
        mul_factor = min(preview_length/env.PREVIEW_DIVISOR, 1)
        f_score = relevance_score + (abs_diff * mul_factor)
    
    else:
        abs_diff = abs(env.MAX_SCORE - relevance_score)
        mul_factor = min(preview_length/env.PREVIEW_DIVISOR, 1)
        f_score = relevance_score + (abs_diff * mul_factor)
        
    return min(f_score, env.MAX_SCORE)


async def get_insertable_data(uid:str, realm:dict) -> dict:
    """
    Find user collection document with space for new file entries.
    
    Identifies user collection documents that have room for additional
    file entries (less than 50 files per document).
    
    Args:
        uid (str): User identifier
        realm (dict): Realm filter parameters
        
    Returns:
        dict: User collection document with available space, or empty dict
    """
    
    pipeline = await get_insertable_data_pipeline(uid=uid, realm=realm)
    data = [i async for i in await db.user_collection.aggregate(pipeline=pipeline, allowDiskUse=True)]
    return data[0] if data else {}
        
        
async def delete_index_data(index, filter:dict):
    """
    Remove documents from the inverted index based on filter criteria.
    
    Finds documents matching the filter and removes them from the
    inverted index to maintain search consistency.
    
    Args:
        index: Inverted index instance
        filter (dict): Filter criteria for documents to remove
        
    Returns:
        None
    """
    
    logger.debug(f"filters : {filter}")
    ids = [i["_id"] for i in await db.vector_store.find(filter, {"_id":1}).to_list()]
    
    async with asyncio.Lock():
        
        logger.debug(f"filtered_ids : {ids}")
        
        for i in ids:
            out = index.search_field("title", i)
            for i in out:
                try:
                    async with asyncio.Lock():
                        index.remove_document(i)
                except Exception as e:
                    logger.debug(f"skipped id: {i}")
        
    return None


async def _stream_response(correlation_id:str, replyq_name:str):
    """
    Stream responses from a reply queue with correlation ID matching.
    
    Generator that yields parsed JSON responses from RabbitMQ reply queue,
    cleaning up the queue when processing is complete.
    
    Args:
        correlation_id (str): Unique identifier for message correlation
        replyq_name (str): Name of the reply queue
        
    Yields:
        dict: Parsed JSON response data from the queue
    """
    
    data = get_msg_from_reply_queue(
        reply_name_name=replyq_name, correlation_id=correlation_id
    )

    async for message in data:
        clean_message = message.lstrip("data: ").strip()
        data_a = json.loads(clean_message)
        
        yield data_a

        if data_a["data"]["done"]:
            await delete_reply_queue(queue_name=replyq_name)
            break