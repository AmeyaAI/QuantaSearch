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
import re
import time
import string
import asyncio
import nest_asyncio
from nltk.corpus import stopwords

from llama_index.core.workflow import Workflow
from llama_index.core.workflow import step, StartEvent, StopEvent, Context

from db.db import db
import utils.util as ut
from db.redis import cache
from utils.load_envs import env
from logger.logger import logger
from core.mongo_vector import create_mongodb_atlas_indexes
from core.inverted_index_retiver import index_retriver, fetch_docs_optimized
from core.file_preview import process_texts, get_preview_docs, find_occurrences
from utils.pipelines import get_list_files_pipeline

from fast_inverted_index import (
    Index, Schema, FieldSchema
)

nest_asyncio.apply()

INDEX_STORAGE_PATH = env.INVERTED_INDEX_PATH or "ameya-inverted-index/fast-index-storage"
SEARCH_THRESHOLD = env.RETRIVER_CUT_OFF_THRESH
LONG_TEXT_LIMIT = 5

os.environ["MONGODB_URI"] = env.MONGODB_URI

lock = asyncio.Lock()
LAST_INDEX_NUM = env.LAST_INDEX_NUM
pattern = re.compile(r'[^A-Za-z0-9 ]+')
stop_words = set(stopwords.words('english'))
PUNCT_RE = re.compile("[" + re.escape(string.punctuation) + "]")


schema = Schema()
schema.add_field(FieldSchema.keyword("title"))
schema.add_field(FieldSchema.text("content"))
schema.add_field(FieldSchema.keyword("meta"))
schema.set_default_field("content")


    
async def index_lister():
    return [i async for i in await db.vector_store.list_search_indexes()]

if asyncio.run(index_lister()):
    asyncio.run(create_mongodb_atlas_indexes(1536))
    logger.info("Completed creating indexes.")
else:
    logger.error("Failed to create indexes.")
    raise Exception("Failed to create indexes.")




class Filelist(Workflow):
    
    @step(num_workers=5)
    async def get_file_list(self, ev:StartEvent) -> StopEvent:
        """Retrive the user file list data."""

        logger.info(f"Started getting the user file list for uid : {ev.uid}.")
        try:
            _data = [i async for i in db.user_collection.find({"uid":ev.uid})]
            _r_keys = []
            
            if not _data:
                return StopEvent(result=(True, []))
            
            for i in _data:
                _r_keys.extend(i["r_keys"])
            
            flt = {"uid":ev.uid}
            
            if ev.realm:
                assert not set(list(ev.realm.keys())).difference(set(_r_keys)), "Unknown realm key is used for filter data."

                flt.update({f"realm.{k}": v for k,v in ev.realm.items()})   
            
            list_files_pipeline = await get_list_files_pipeline(flt)
            files_list = [i async for i in await db.user_collection.aggregate(list_files_pipeline)]
                
            logger.info(f"Completed getting the user file_list for uid : {ev.uid}.")
            
            return StopEvent(result=(True, files_list))
        
        except Exception as e:
            logger.error(f"Error in the get_file_list event. Error: {e.__class__.__name__} :- {str(e)}")
            return StopEvent(result=(False, f"{e.__class__.__name__} : {str(e)}"))





class MetaUpdater(Workflow):
    """This workflow is used to update the metadata of the documents."""
    
    @step(num_workers=5)
    async def update_meta(self, ev:StartEvent) -> StopEvent:
        """This step is used to update the metadata of the documents."""
        logger.info(f"Started metadata update event.........")

        try:
            logger.debug("Checking version and realm creaditability........")
            
            assert await ut.check_realm_keys(db.user_collection, ev.uid, ev.realm, False), "realm attributes does not match or no data to process."
            
            cur_version, versions = await ut.get_doc_lt_version(db.user_collection, ev.uid, ev.realm, ev.document_id)
            
            if cur_version == ev.latest_version:
                return StopEvent(result=(True, "Skipping the version change as the current version is same as the latest version."))

            assert cur_version is not None or versions, f"There is no current version selected, please publish file to set current version. You must need atleast 1 published file to change versions."
            assert ev.latest_version in versions, f"Version_id not found. Please upload the document with the new version_id : {ev.latest_version}."

            logger.debug("Completed version creaditability.")
            logger.debug(f"Started user_collection update for uid : {ev.uid}....")
            
            if ev.latest_version == 0:
                ev.latest_version = None

            await db.user_collection.update_one({"uid": ev.uid, "realm":ev.realm},
                                                {"$set": {f"files.{ev.document_id}.current_version": ev.latest_version,
                                                          f"files.{ev.document_id}.version_change_date": ev.version_change_date}})

            filter = {"metadata.uid": ev.uid, "metadata.realm":ev.realm, "metadata.document_id": ev.document_id}
            update = {"$set": {"metadata.version_change_date": ev.version_change_date}}
            
            logger.debug(f"Started vector_collection update for uid : {ev.uid}")
            
            ret = await db.vector_store.update_many(filter, update)
            
            if ev.latest_version is not None:
                await db.vector_store.update_many({"metadata.uid": ev.uid, "metadata.realm":ev.realm,
                                                   "metadata.document_id": ev.document_id, 
                                                   "metadata.version_id": {"$nin": [0, ev.latest_version]}},
                                                  {"$set": {"metadata.state": "inter"}})
                
                await db.vector_store.update_many({"metadata.uid": ev.uid, "metadata.realm":ev.realm,
                                                   "metadata.document_id": ev.document_id, 
                                                   "metadata.version_id": ev.latest_version},
                                                  {"$set": {"metadata.state": "Publish"}})
            
            else:
                await db.vector_store.update_many({"metadata.uid": ev.uid, "metadata.realm":ev.realm,
                                                   "metadata.document_id": ev.document_id, 
                                                   "metadata.version_id": {"$ne": 0}},
                                                  {"$set": {"metadata.state": "inter"}})

            logger.debug(f"Completed user and vector collection update for uid : {ev.uid}")
            logger.debug(f"Total documents updated: {ret.modified_count}")
            logger.info(f"Completed metadata update event for {ev.uid}.")
            
            try:
                await cache.delete_one(ev.uid)
            except Exception as e:
                logger.warning(f"Failed to delete cache for uid: {ev.uid}. Error: {e}")
                
            return StopEvent(result=(True, "Metadata updated successfully."))
            
        except Exception as e:
            logger.error(f"Error in the metadata update event. Error: {e.__class__.__name__} :- {str(e)}")
            return StopEvent(result=(False, f"{e.__class__.__name__} :- {str(e)}"))



class FileSearcher(Workflow):
    """This workflow is used to search the files."""
    
    @step(num_workers=5)
    async def search_files(self, ev: StartEvent) -> StopEvent:
        """This step is used to search the files."""
        start = time.time()
        logger.info(f"Started querying preprocess for uid: {ev.uid}")
        
        query__ = ev.query.strip().lower()
        contains_sc = bool(PUNCT_RE.search(query__))
        tot_doc = await ut.get_total_doc(ev.uid)
        logger.debug(f"the total docs is : {tot_doc}")
        
        query_ = query__.replace('"',"").replace("'","")
        query_ = pattern.sub(" ", query_)

        logger.info(f"Started searching the files for query : {query__}.........")

        try:
            logger.debug("Checking the cache......")
            cached_data = await cache.find_one(ev.uid)
            if (
                cached_data and
                cached_data.get("__td__") == tot_doc and
                cached_data.get("__rlm__") == ev.realm and
                cached_data.get("__st__") == ev.state and
                cached_data.get("__exm__") == ev.exact_match and
                query__ in cached_data
            ):
                return StopEvent(result=(True, cached_data[query__]))
        except Exception as e:
            logger.warning(f"Cache retrieval failed: {e}")

        logger.debug("Searching for the user query......")
        q_s = query_.split()
        query = " ".join([word for word in q_s if word not in stop_words])
        
        if not query and not ev.exact_match:
            return StopEvent(result=(True, []))

        filters = {"metadata.uid": ev.uid, "metadata.state": ev.state}
        out_docs = {"sr_docs": [], "text_search": [], "fts_index": [], "sp_index": []}

        async def _parallel_process(search_type: str):
            try:

                async with asyncio.Lock():
                    
                    index = Index(
                                storage_path=os.path.join(os.getcwd(), INDEX_STORAGE_PATH),
                                cache_size=10000,
                                cache_ttl_secs=600,
                                store_positions=True,
                                in_memory=False,
                                schema=schema,
                            )
                     

                    if search_type == "sp_search":
                        out_result = await index_retriver(index, query=query, 
                                                          search_type=search_type)
                        
                        filters.update({f"metadata.realm.{k}": v for k,v in ev.realm.items()})
                        result = await fetch_docs_optimized(out_result, filters, query)
                    
                    if search_type == "text_search":
                        out_result = await index_retriver(index, query=query_, 
                                                          search_type=search_type)
                        
                        filters.update({f"metadata.realm.{k}": v for k,v in ev.realm.items()})
                        result = await fetch_docs_optimized(out_result, filters, query_)
                    
                    elif search_type == "search":
                        out_result = await index_retriver(index, query=query_, 
                                                          search_type=search_type)
                        
                        filters.update({f"metadata.realm.{k}": v for k,v in ev.realm.items()})
                        _result = await fetch_docs_optimized(out_result, filters, query_)
                        
                        result = [i for i in _result if query__ in i["text"].lower()]
                    
                out_docs[{
                    "search": "fts_index",
                    "sp_search": "sp_index",
                    "text_search": "text_search"
                }[search_type]].extend(result)
            except Exception as e:
                logger.warning(f"{search_type} retrieval failed: {e}")

        st = time.time()

        logger.debug("Initaiating parallel retrival process......")
        
        if ev.exact_match:
            search_type = "search"
        
        else:
            search_type = "sp_search"
        
        await _parallel_process(search_type)
        logger.debug("Completed parallel retrival process.")
        
        sr_docs_combined = out_docs["fts_index"] + out_docs["sp_index"] + out_docs["text_search"]
        file_scores = {}
        
        logger.debug("Performing scroes aggregation......")
        for doc in sr_docs_combined:
            name = doc["document_name"]
            score = doc["relavence_score"]
            if name not in file_scores:
                file_scores[name] = {
                    "score": score,
                    "count": 1,
                    "data": [doc],
                }
            else:
                file_scores[name]["score"] += score
                file_scores[name]["count"] += 1
                file_scores[name]["data"].append(doc)
                

        logger.debug("Completed performing scroes aggregation.")
        
        temp = {}
        fl_score_len = len(file_scores)
        divider = sum(bool(out_docs[k]) for k in ["fts_index", "sp_index"]) or 1
        logger.debug(f"divider : {divider}")
        logger.debug(f"Performing score assignment....")
        
        
        for key, val in file_scores.items():
            
            avg_score = round(ut.compute_score(val["count"], 
                                        fl_score_len, 
                                        base_score=env.BASE_SCORE), 6)
            
            if avg_score > SEARCH_THRESHOLD:
                
                texts = [i["text"].replace(f"file name : {i['document_name']}", "") for i in val["data"]]
                
                preview = process_texts(texts, query__, int(env.PREVIEW_LENGTH),
                                        limit=int(env.MAX_PREVIEW_COUNT))
                
                computed_score = ut.compute_preview_score(avg_score, len(preview))
                out_data = val["data"][0]
                out_data["relavence_score"] = round((computed_score * 100) , 3)
                out_data["preview"] = preview
                
                out_data.pop("text", None)
                
                if ev.exact_match and key not in temp and preview:
                    temp[key] = out_data
                    
                elif not ev.exact_match and key not in temp:
                    temp[key] = out_data

        logger.debug("Completed assigning scroes.")
        
        final_docs = list(temp.values())
        final_docs.sort(key=lambda x: x["relavence_score"], reverse=True)
        
        final_docs = final_docs[:env.MAX_DOC_LIMIT]

        ed = time.time()
        logger.debug(f"f_docs : {len(final_docs)}, tot_docs : {tot_doc}")
        logger.debug(f"Loading retriever data..........{ed - st}")
        logger.info(f"time-taken to complete is {ed - start} seconds.")

        cache_data = {
            query__: final_docs,
            "__td__": tot_doc,
            "__rlm__": ev.realm,
            "__st__": ev.state,
            "__exm__": ev.exact_match
        }

        await cache.insert_one(ev.uid, cache_data, 3600)
        return StopEvent(result=(True, final_docs))
    

class FileSearcherPreview(Workflow):
    
    @step(num_workers=5)
    async def get_preview(self, ctx:Context, ev:StartEvent) -> StopEvent:
        
        try:
            logger.info(f"Started getting docs for uid : {ev.uid}")
            logger.debug(f"Started fetching the document with doc_id: {ev.document_id}")
            
            docs = await get_preview_docs(ev.uid, ev.realm, ev.document_id, ev.state)
            
            logger.debug(f"Total number of fetched docs: {len(docs)}")
            
            st=time.time()
            query = ev.query.lower()
            
            if docs:
                preview = process_texts(docs, query, int(env.PREVIEW_LENGTH), limit=-1, max_workers=4,
                                        detailed_output=True)
                
                if preview and isinstance(preview[0], dict):
                    preview = sorted(preview, key=lambda x: x["page_no"])
                    
            else:
                logger.warning(f"The docs is returned empty.")
                preview = []  
            ed = time.time()
            
            logger.debug(f"Preview time for parallel : {ed-st}")
            return StopEvent(result=(True, {"preview_texts": preview}))
        
        except Exception as e:
            logger.error(f"The Previer event generated an error. The error is : {str(e)}")
            return StopEvent(result=(False, f"{e.__class__.__name__} :- {str(e)}"))