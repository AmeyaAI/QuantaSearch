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


import os
import uuid
import asyncio
from typing import Any
from llama_index.core import Document
from pymongo.asynchronous.collection import AsyncCollection

from db.db import db
from logger.logger import logger
from utils.pipelines import get_insertable_data_pipeline


def add_metadata(doc:Document, ev:Any) -> Document:
    """
    Add comprehensive system metadata to a document object.
    
    Enriches document with user information, version details, realm data, processing state,
    and other system metadata. Prepends filename to document text content.
    
    Args:
        doc (Document): LlamaIndex Document object to enrich
        ev (Any): Event object containing metadata information
        
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
    
    Queries user collection to get version information for document management,
    validation, and version control operations.
    
    Args:
        collection (AsyncCollection): MongoDB user collection reference
        uid (str): User identifier
        realm (dict): Realm filter parameters
        doc_id (str): Document identifier
        
    Returns:
        tuple[list, list]: (current_version, available_versions) or ([], []) if not found
    """
     
    data = await collection.find_one({"uid": uid, "realm":realm, f"files.{doc_id}": {"$exists":True}})

    try:
        return data["files"][doc_id]["current_version"], data["files"][doc_id]["versions"]
        
    except Exception as e:
        return [], []
    


async def check_realm_keys(collection:AsyncCollection, uid:str, realm:dict, upload:bool) -> bool:
    """
    Validate realm keys against user's registered realm configuration.
    
    Ensures provided realm keys match the user's configured realm keys
    for data consistency and access control validation.
    
    Args:
        collection (AsyncCollection): MongoDB user collection reference
        uid (str): User identifier
        realm (dict): Realm parameters to validate
        upload (bool): Whether this is for upload operation context
        
    Returns:
        bool: True if realm keys are valid, False otherwise
    """
    
    data = await collection.find_one({"uid":uid, "realm":realm})
    rlm_keys = list(realm.keys())
    
    if data is not None:
        return not bool(set(rlm_keys).symmetric_difference(data["r_keys"]))
    else:
        return upload
    
    
async def get_file_upload_date(collection:AsyncCollection, doc_id:str, uid:str, realm:dict) -> str | int:
    """
    Retrieve the original upload date for a specific document.
    
    Queries vector store metadata to get the document's upload timestamp
    for date tracking and display purposes.
    
    Args:
        collection (AsyncCollection): MongoDB vector store collection reference
        doc_id (str): Document identifier
        uid (str): User identifier
        realm (dict): Realm filter parameters
        
    Returns:
        str | int: Upload date as string or timestamp, empty string if not found
    """
    
    data = await collection.find_one({"metadata.uid": uid, "metadata.realm": realm,
                                      "metadata.document_id": doc_id, 
                                      })
    
    try:
        return data["metadata"]["uploaded_date"]
    
    except Exception as e:
        return ""
    

async def get_total_doc(uid:str) -> int:
    """
    Get the total number of vector documents for a user.
    
    Retrieves cached document count from user collection for scaling
    and performance optimization purposes.
    
    Args:
        uid (str): User identifier
        
    Returns:
        int: Total number of vector documents, 0 if not found
    """
    
    doc = await db.user_collection.find_one({"uid": uid})
    tc_doc = doc if doc else {}
    return tc_doc.get("total_vdocs", 0)


async def get_insertable_data(uid:str, realm:dict) -> dict:
    """
    Find user collection document with available space for new file entries.
    
    Executes aggregation pipeline to identify user documents that can accommodate
    additional file entries without exceeding the 50-file limit.
    
    Args:
        uid (str): User identifier
        realm (dict): Realm filter parameters
        
    Returns:
        dict: User collection document with available space, or empty dict if none found
    """
    
    pipeline = await get_insertable_data_pipeline(uid=uid, realm=realm)
    data = [i async for i in await db.user_collection.aggregate(pipeline=pipeline, allowDiskUse=True)]
    return data[0] if data else {}
        
        
async def delete_index_data(index, filter:dict):
    """
    Remove documents from the inverted index based on filter criteria.
    
    Queries vector store with filters, finds matching documents in the inverted index,
    and removes them to maintain search index consistency.
    
    Args:
        index: Fast inverted index instance
        filter (dict): Filter criteria for documents to remove from index
        
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


def get_folder_size(path) -> int:
    """
    Calculate the total size of a file or directory in bytes.
    
    Recursively calculates size for directories, handles individual files,
    includes error handling for inaccessible files, and validates path existence.
    
    Args:
        path (str): File or directory path to calculate size for
        
    Returns:
        int: Size in bytes, 0 if path doesn't exist
        
    Raises:
        RuntimeError: If path is neither file nor directory, or if calculation fails
    """
    
    try:
        if not os.path.exists(path):
            return 0
        
        if os.path.isfile(path):
            return os.path.getsize(path)
        
        elif os.path.isdir(path):
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(file_path)
                    except (OSError, IOError):
                        continue
            return total_size
        
        else:
            raise RuntimeError(f"Path is neither a file nor a directory: {path}")
            
    except Exception as e:
        raise RuntimeError(f"Error calculating size for {path}: {str(e)}")


def _get_job_data() -> dict:
    """
    Generate default job configuration for document processing.
    
    Creates standardized job data structure with default settings for OCR,
    LLM, embedding, database configuration, and processing parameters.
    
    Returns:
        dict: Job configuration dictionary with default values
    """
    
    return {
            "job_id": str(uuid.uuid4()),
            "file_path": [],
            "settings": {
                "ocr": True,
                "llm": {
                    "provider": "",
                    "model": "",
                    "api_key": ""
                },
                "embedding": {
                    "provider": "",
                    "model": "",
                    "api_key": ""
                },
                "llama_api_key": "",
                "extraction_type": ""
            },
            
            "db_config": {
                "db_provider": "",
                "db_name": "",
                "db_url": "",
                "collection_name": ""
            },
            "service_name": "doc-search",
            "result_type": "text",
        }


    
async def store_index(index_name:str):
    """
    Store index backup to cloud storage (placeholder implementation).
    
    Reserved for future implementation of cloud-based index backup functionality.
    
    Args:
        index_name (str): Name of the index backup to store
    """
    pass 