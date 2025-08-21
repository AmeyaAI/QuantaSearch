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


import re
import math
import json
import asyncio
import requests
import subprocess
from typing import Any
from llama_index.core import Document
from pymongo.asynchronous.collection import AsyncCollection

from db.db import db
from utils.load_envs import env
from logger.api_logger import logger
from utils.pipelines import get_insertable_data_pipeline
from event_driven.producer import get_msg_from_reply_queue, delete_reply_queue


def add_metadata(doc:Document, ev:Any) -> Document:
    '''Add metadata to the given Document object.
    
    Args:
        - doc (Document) : The document object to add metadata.
        - data (Any) : The datas of the user.
    
    Returns:
        - Document
    '''
    
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
    data = await collection.find_one({"uid": uid, "realm":realm, f"files.{doc_id}": {"$exists":True}})

    try:
        return data["files"][doc_id]["current_version"], data["files"][doc_id]["versions"]
        
    except Exception as e:
        return [], []
    


async def check_realm_keys(collection:AsyncCollection, uid:str, realm:dict, upload:bool) -> bool:
    
    data = await collection.find_one({"uid":uid, "realm":realm})
    rlm_keys = list(realm.keys())
    
    if data is not None:
        return not bool(set(rlm_keys).symmetric_difference(data["r_keys"]))
    else:
        return upload
    
    
async def get_file_upload_date(collection:AsyncCollection, doc_id:str, uid:str, realm:dict) -> str | int:
    data = await collection.find_one({"metadata.uid": uid, "metadata.realm": realm,
                                      "metadata.document_id": doc_id, 
                                      })
    
    try:
        return data["metadata"]["uploaded_date"]
    
    except Exception as e:
        return ""


def find_whitespace_around_queries(text, query):
    pattern = re.escape(query)
    
    matches = list(re.finditer(pattern, text))
    if not matches:
        return []

    results = []
    for match in matches:
        start_pos = match.start()
        end_pos = match.end()

        whitespaces_before = list(re.finditer(r'\s', text[:start_pos]))
        if len(whitespaces_before) >= int(env.PREVIEW_LENGTH)+1:
            fourth_whitespace_before = whitespaces_before[-(int(env.PREVIEW_LENGTH)+1)].start()
        else:
            fourth_whitespace_before = 0

        whitespaces_after = list(re.finditer(r'\s', text[end_pos:]))
        if len(whitespaces_after) >= int(env.PREVIEW_LENGTH)+1:
            fourth_whitespace_after = end_pos + whitespaces_after[int(env.PREVIEW_LENGTH)].start()
        else:
            fourth_whitespace_after = len(text)

        results.append({
            "query_start": start_pos,
            "query_end": end_pos,
            "fourth_whitespace_before": fourth_whitespace_before,
            "fourth_whitespace_after": fourth_whitespace_after
        })

    return results


async def get_total_doc(uid:str) -> int:
    doc = await db.user_collection.find_one({"uid": uid})
    tc_doc = doc if doc else {}
    return tc_doc.get("total_vdocs", 0)


async def get_file_status(uid:str, document_id:str) -> str:
    res = await db.user_collection.find_one({"uid": uid, f"files.{document_id}": {"$exists":True}}, {"files":1})
    return res["files"][document_id].get("status", "Not Found")


def compute_score(doc_count, estimated_max=1000, base_score=0.7):
    if doc_count < 0:
        raise ValueError("doc_count must be non-negative")

    log_count = math.log(1 + doc_count)
    log_max = math.log(1 + estimated_max)
    scale = log_count / log_max
    rank = base_score + (1 - base_score) * scale
    return min(rank, 0.9995)


def compute_preview_score(relevance_score:float, preview_length:int):
    
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


async def get_insertable_data(uid:str, realm:dict):
    pipeline = await get_insertable_data_pipeline(uid=uid, realm=realm)
    data = [i async for i in await db.user_collection.aggregate(pipeline=pipeline, allowDiskUse=True)]
    return data[0] if data else {}
        
        
async def delete_index_data(index, filter:dict):
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


def get_folder_size(path):
    result = subprocess.run(['du', '-sb', path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0:
        size_str = result.stdout.split()[0]
        return int(size_str)
    else:
        raise RuntimeError(f"Error: {result.stderr.strip()}")
    
    
async def store_index(index_name:str):
    pass 


async def _stream_response(correlation_id:str, replyq_name:str):
    
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