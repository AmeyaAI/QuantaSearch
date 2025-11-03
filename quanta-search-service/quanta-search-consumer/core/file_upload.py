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
import shutil
import asyncio
import nest_asyncio
from datetime import datetime
from llama_index.core.workflow import Workflow, StartEvent, StopEvent, Context, step

from db.db import db
from db.redis import cache
from utils import util as ut
from utils.load_envs import env
from logger.logger import logger
from core.extractor import FileExtractors
from utils.aws_s3 import download_from_presigned
from schemas.schema import (
    ProgressEvent,
    FileParseEvent,
    MetaUpdateEvent,
    IndexUpdateEvent,
    VectorUploadEvent,
    UserCollectionUpdateEvent,
)

from fast_inverted_index import (
    Index, Schema, FieldSchema
)

nest_asyncio.apply()

lock = asyncio.Lock()
extractor = FileExtractors()
LAST_INDEX_NUM = env.LAST_INDEX_NUM
INDEX_STORAGE_PATH = env.INVERTED_INDEX_PATH or "ameya-inverted-index/fast-index-storage"

schema = Schema()
schema.add_field(FieldSchema.keyword("title"))
schema.add_field(FieldSchema.text("content"))
schema.add_field(FieldSchema.keyword("meta"))
schema.set_default_field("content")



class FileSearcherUpload(Workflow):
    """This workflow is used to upload the files to the vector database."""


    @step(num_workers=5)
    async def download_files(self, ctx:Context, ev:StartEvent) -> FileParseEvent | StopEvent:
        """This step is used to download the files from s3."""

        logger.info("Started downloading the files from s3.........")

        try :
            if ev.state == "Publish":
                assert ev.version_id != 0 , "During Publishment of the document the version id must be not 0."
                assert ev.version_id != "0" , "During Publishment of the document the version id must be not 0."
            
            elif ev.state == "Draft":
                ev.version_id = 0
                
            inp_len = len(ev.s3_file_path)
            
            if await db.user_collection.find_one({"uid":ev.uid, "realm": ev.realm}):
                for idx, i in enumerate(ev.document_id):   
                    logger.debug(f"Checking the version staus for uid : {ev.uid} with version id : {ev.version_id}")

                    _, versions = await ut.get_doc_lt_version(db.user_collection, ev.uid, ev.realm, i)
                    print(versions)
                    print(ev.uid, ev.realm, i)

                    if ev.version_id is not None and versions and ev.version_id in versions:
                        logger.debug(f"Skipping the {ev.state} upload process as the version is already there.")
                        ev.document_id.pop(idx)
                        ev.s3_file_path.pop(idx)
                
                if not ev.document_id and not ev.s3_file_path:
                    return StopEvent(result=(True, f"Skipping the {ev.state} upload process as the version is already there.", ["success" for _ in range(inp_len)]))


            ret, f_meta = await download_from_presigned(ev.s3_file_path, ev.uid, ev.document_id, ev.event_id)
            dir_path = ret[0]["dir_path"]
            
            file_datas = []
            
            for i in ret:
                if i["error"] is not None and os.path.exists(i["file_path"]):
                    os.remove(i["file_path"])
                else:
                    file_datas.append(i)
                
            logger.info("Completed downloading the files from s3.")

            if ev.state == "Draft":
                return FileParseEvent(dir_path=dir_path, file_urls=file_datas, file_meta=f_meta, uid=ev.uid, 
                                      version_id=ev.version_id, uploaded_date=ev.uploaded_date,
                                      state=ev.state, realm=ev.realm, user_id=ev.user_id,
                                      parser_type=ev.parser_type, parser_mode=ev.parser_mode)
            
            elif ev.state == "Publish":
                return FileParseEvent(dir_path=dir_path, file_urls=file_datas, file_meta=f_meta, uid=ev.uid,
                                      version_id=ev.version_id, published_date=ev.published_date,
                                      state=ev.state, realm=ev.realm, user_id=ev.user_id,
                                      parser_type=ev.parser_type, parser_mode=ev.parser_mode)
        
        except Exception as e:
            logger.error(f"Error in downloading the files from s3. Error: {e.__class__.__name__} :- {str(e)}")
            return StopEvent(result=(False, f"{e.__class__.__name__} :- {str(e)}", None))



    @step(num_workers=5)
    async def parse_file(self, ctx:Context, ev:FileParseEvent) -> MetaUpdateEvent | StopEvent:
        """This step is used to parse the files from the directory."""
        
        logger.info("Started initial file parse event.........")
        try:
            assert os.path.isdir(ev.dir_path) and os.path.exists(ev.dir_path), "The dir_path must be a path to the directory and exists."
            
            logger.debug(f"Started parsing the files from the directory {ev.dir_path}.......")
            
            docs = []
            
            for j in ev.file_urls:
                logger.debug(f"Processing '{j['file_path']}' file for uid: {ev.uid}.")
                
                d_cs = await extractor.aload_data(j["file_path"], j["file_name"], j["checksum"], j["url"])
                
                logger.debug(f"Completed processing '{j['file_path']}' file for uid: {ev.uid}.")
                
                if d_cs:
                    docs.extend(d_cs)
                    ev.file_meta[j["file_name"]]["status"] = "Success"
                else:
                    ev.file_meta[j["file_name"]]["status"] = "Failed"

            if docs:
                logger.debug(f"Started removing the files from temp folder for uid: {ev.uid}.........")
                
                for i in os.listdir(ev.dir_path):
                    if os.path.exists(os.path.join(ev.dir_path, i)):
                        os.remove(os.path.join(ev.dir_path, i))
                
                if len(os.listdir(ev.dir_path)) == 0:
                    shutil.rmtree(ev.dir_path)
                    
                logger.debug(f"Completed removing files from temp folder for uid: {ev.uid}.")
            
            else:
                logger.error("There is no documents extracted for the uploaded file. Please reupload the file.")
                return StopEvent(result=(False, "There is no documents extracted for the uploaded file. Please reupload the file.", None))


            logger.info("Completed parsing the files from the directory.")
            
            if ev.state == "Draft":
                return MetaUpdateEvent(docs=docs, uid=ev.uid, version_id=ev.version_id,
                                       file_meta=ev.file_meta, uploaded_date=ev.uploaded_date,
                                       state=ev.state,realm=ev.realm, user_id=ev.user_id)
            
            elif ev.state == "Publish":
                return MetaUpdateEvent(docs=docs, uid=ev.uid, version_id=ev.version_id,
                                       file_meta=ev.file_meta, published_date=ev.published_date,
                                       state=ev.state, realm=ev.realm, user_id=ev.user_id)
        
        except Exception as e:
            logger.error(f"Error in the initial file upload event. Error: {e.__class__.__name__} :- {str(e)}")
            logger.debug(f"Started removing the files from temp folder for uid: {ev.uid}.........")
                
            for i in os.listdir(ev.dir_path):
                os.remove(os.path.join(ev.dir_path, i))
            
            if len(os.listdir(ev.dir_path)) == 0:
                shutil.rmtree(ev.dir_path)
                
            logger.debug(f"Completed removing files from temp folder for uid: {ev.uid}.")
            return StopEvent(result=(False, f"{e.__class__.__name__} :- {str(e)}", None))
    


    @step(num_workers=5)
    async def meta_update(self, ctx:Context, ev:MetaUpdateEvent) -> UserCollectionUpdateEvent | StopEvent:
        """This step is used to add the metadata to the documents."""
        
        logger.info("Started metadata update event.........")
        
        try:
            for k,v in ev.file_meta.items():
                upload_date = await ut.get_file_upload_date(db.vector_store, v["document_id"], ev.uid, ev.realm)
                dock_check =  await ut.get_doc_lt_version(db.user_collection, ev.uid, ev.realm, v["document_id"])
                
                ev.file_meta[k]["published_date"] = ev.published_date
                
                if not ev.uploaded_date:
                    ev.file_meta[k]["uploaded_date"] = ev.published_date if (ev.state == "Publish" and not dock_check[1]) else upload_date
                    
                else:
                    ev.file_meta[k]["uploaded_date"] = ev.uploaded_date
            
            logger.debug(f"The len of docs ---------> {len(ev.docs)}")
            
            docs = [ut.add_metadata(i, ev) for i in ev.docs]
            
            logger.debug("Completed metadata update event.")
            logger.debug(f"The len of docs ---------> {len(docs)}")
        
            if not docs:
                logger.error("Thers is no docs to process.")
                return StopEvent(result=(False, "Thers is no docs to process.", None))
            
            return UserCollectionUpdateEvent(docs=docs, uid=ev.uid, state=ev.state, version_id=ev.version_id,
                                            file_meta=ev.file_meta, realm=ev.realm)
        
        except Exception as e:
            logger.error(f"Error in metaupdate Event. Error: {e.__class__.__name__} :- {str(e)}")
            return StopEvent(result=(False, f"Error in metaupdate Event. Error: {e.__class__.__name__} :- {str(e)}", None))

        
    @step(num_workers=5)     
    async def user_collection_update(self, ctx:Context, ev:UserCollectionUpdateEvent) -> VectorUploadEvent | StopEvent:
        """This step is used to update the user collection in the database."""
        
        try:
            r_keys = list(ev.realm.keys())
            docs_len = len(ev.docs)
            
            for k,v in ev.file_meta.items():
                
                if v["status"] == "Success":
                    _data = await db.user_collection.find_one({"uid": ev.uid, "realm":ev.realm})
                    total_docs = await ut.get_total_doc(uid=ev.uid)
                    
                    if not _data and ev.docs:

                        logger.debug(f"Creating user data in user_collection for uid : {ev.uid}.")    
                        logger.debug(f"Uploading file data to user_collection for doc_id : {v['document_id']}.")
                        
                        await db.user_collection.insert_one({"uid": ev.uid, "r_keys" : r_keys, "realm": ev.realm,
                                                            "total_vdocs": total_docs + docs_len,
                                                            "files": {v["document_id"]: {"current_version": ev.version_id if ev.state=="Publish" else None,
                                                                                        "versions": [ev.version_id],
                                                                                        "status":"Processing",
                                                                                        "file_name": k,
                                                                                        "uploaded_date": v["uploaded_date"],
                                                                                        "published_date": v["published_date"],
                                                                                        "version_change_date": ev.docs[0].metadata["version_change_date"]}}})
                            

                        logger.debug("Created user data in user_collection.")
                
                
                    elif _data and ev.docs:

                        logger.debug(f"Updating user data in user_collection for uid: {ev.uid}.")     
                        logger.debug(f"Updating file data to user_collection for doc_id : {v['document_id']}.")
                        
                        ins_point = await ut.get_insertable_data(ev.uid, ev.realm)
                    
                        if ins_point:
                            await db.user_collection.update_one({"_id": ins_point["_id"]},
                                                                {"$set": {"total_vdocs": _data["total_vdocs"] + docs_len,
                                                                        f"files.{v['document_id']}.current_version": ev.version_id if ev.state=="Publish" else None,
                                                                        f"files.{v['document_id']}.status": "Processing",
                                                                        f"files.{v['document_id']}.file_name": k,
                                                                        f"files.{v['document_id']}.uploaded_date": v["uploaded_date"],
                                                                        f"files.{v['document_id']}.published_date": v["published_date"],
                                                                        f"files.{v['document_id']}.version_change_date": ev.docs[0].metadata["version_change_date"]},        
                                                                "$push": {f"files.{v['document_id']}.versions": ev.version_id}})
                        
                        else:
                            await db.user_collection.insert_one({"uid": ev.uid, "r_keys" : r_keys, "realm": ev.realm,
                                                        "total_vdocs": total_docs + docs_len,
                                                        "files": {v["document_id"]: {"current_version": ev.version_id if ev.state=="Publish" else None,
                                                                                    "versions": [ev.version_id],
                                                                                    "status":"Processing",
                                                                                    "file_name": k,
                                                                                    "uploaded_date": v["uploaded_date"],
                                                                                    "published_date": v["published_date"],
                                                                                    "version_change_date": ev.docs[0].metadata["version_change_date"]}}})
                        
                        if ev.state == "Publish":   
                            await db.vector_store.update_many({"metadata.uid":ev.uid, "metadata.realm":ev.realm,
                                                            "metadata.document_id": v["document_id"],
                                                            "metadata.version_id": {"$nin": [0, ev.version_id]}},
                                                            {"$set": {"metadata.state": "inter"}})
                        
                        logger.info("Updated user data in user_collection.")
                    
                    else:
                        logger.error("Thers is no docs to update the collection.")
                        return StopEvent(result=(False, "Thers is no docs to update the collection.", None))
                
            await ctx.set("file_meta", ev.file_meta)
            
            return VectorUploadEvent(docs=ev.docs, uid=ev.uid)
        
        except Exception as e:
            logger.error(f"Error in collection update Event. Error: {e.__class__.__name__} :- {str(e)}")
            return StopEvent(result=(False, f"Error in collection update Event. Error: {e.__class__.__name__} :- {str(e)}", None))



    @step(num_workers=5)
    async def vector_upload(self, ctx:Context, ev:VectorUploadEvent) -> IndexUpdateEvent | StopEvent:
        """This step is used to create the vector index from the documents."""
        
        logger.info("Started vector upload event.........")

        try:
            docs = []

            for _i in ev.docs:
                if _i.text_resource.text:
                    
                    if "docs" in _i.metadata.keys():
                        del _i.metadata["docs"]
                    
                    data = {"_id": str(uuid.uuid4()), "embedding": None,
                            "text": _i.text_resource.text.lower().replace("\n", " "),
                            "metadata": _i.metadata}
                    
                    docs.append(data)
            
            ret = await db.vector_store.insert_many(docs)

            if ret.acknowledged:
                logger.debug(f"Total documents uploaded: {len(ret.inserted_ids)}")
                logger.info("Completed vector upload event.")
                
                try:
                    await cache.delete_one(ev.uid)
                except Exception as e:
                    logger.warning(f"Failed to delete cache for uid: {ev.uid}. Error: {e}")
                
                return IndexUpdateEvent(docs=docs, uid=ev.uid, ids=ret.inserted_ids)
            
            else:
                logger.error(f"Error in the vector upload event. Error: {ret}")
                return StopEvent(result=(False, "Upload Failed.", None))
        
        except Exception as e:
            logger.error(f"Error in the vector upload event. Error: {e.__class__.__name__} :- {str(e)}")
            return StopEvent(result=(False, f"{e.__class__.__name__} :- {str(e)}", None))

    @step(num_workers=5)
    async def update_index(self, ctx:Context, ev:IndexUpdateEvent) -> StopEvent:
        """This step is used to update the local index."""
        
        logger.info("Started Index update event.........")

        try:
            file_meta = await ctx.get("file_meta", None)
            optimize = False
            logger.debug("Fetching Index stats.........")
            logger.debug(f"ids_list : {ev.ids}")
            cache_last_id = await cache.find_one("last_index_id")
            
            index_db_size = ut.get_folder_size(os.path.join(os.getcwd(), INDEX_STORAGE_PATH))
            
            store_index = False
            backup_name = env.INDEX_BACKUP_NAME
            if index_db_size % env.INDEX_BACKUP_MAX_SIZE == 0:
                store_index = True
                backup_name = backup_name +"_"+ str(int(index_db_size / env.INDEX_BACKUP_MAX_SIZE))
            
            async with lock:
                
                index = Index(
                            storage_path=os.path.join(os.getcwd(), INDEX_STORAGE_PATH),
                            cache_size=10000,
                            cache_ttl_secs=600,
                            store_positions=True,
                            in_memory=False,
                            schema=schema,
                        )
                
                stat = index.stats()
                data = [i for i in index.or_query(["name"])]
                _stat = max(data if data else [0])
                
                if not cache_last_id:
                    dt = await db.index_meta_collection.find_one({"backup_name": backup_name})
                    if not dt:
                        _stat = LAST_INDEX_NUM
                    else:
                        _stat = dt["last_index_id"]
                else:
                    _stat = cache_last_id
                
                logger.debug(f"the stat is : {stat}")
                logger.debug(f"the len of doc in index : {len(data)}")
                logger.debug(f"the hihest doc_count : {_stat}")
                
                if _stat % 1000 == 0:
                    optimize = True
                
                logger.debug(f"Index stats : doc_count: {_stat} ")
                logger.debug("Adding documents to index.........")

                docs = [(_stat + idx + 1, {"content": i["text"], "title":i["_id"]})
                        for idx, i in enumerate(ev.docs)
                        ]
                docs = sorted(docs, key=lambda x: x[0])
                logger.debug(f"the docs ids: {[i[0] for i in docs]}")
    
                docs_len = len(docs)
                if docs_len > 200:
                    logger.debug("Using parallel index with batch as 100....")
                    index.add_documents_with_fields_parallel(docs, num_threads=4, batch_size=50)
                    
                elif docs_len > 50:
                    logger.debug("Using parallel index with batch as 25....")
                    index.add_documents_with_fields_parallel(docs, num_threads=4, batch_size=25)
                
                elif docs_len > 25:
                    logger.debug("Using parallel index with batch as 10....")
                    index.add_documents_with_fields_parallel(docs, num_threads=4, batch_size=10)
                
                else:
                    logger.debug("Using non-parallel indexing....")
                    for i in docs:
                        index.add_document_with_fields(*i)
                        
                if optimize or docs[-1][0] % 1000 == 0:
                    index.optimize_parallel(num_threads=4)
                    
                logger.debug(f"The stats after upload : {index.stats()}")
            
            
            im_data = await db.index_meta_collection.find_one({"backup_name": backup_name})
            logger.debug(f"The index meta is {im_data}")
            
            if im_data:
                logger.debug("updating index meta......")
                await db.index_meta_collection.update_one({"_id":im_data["_id"]},
                                                          {"$set": {"last_mongo_id": ev.ids[-1],
                                                                    "last_index_id": docs[-1][0],
                                                                    "modified_time": datetime.now()}})
                logger.debug("updated index meta.")
            else:
                logger.debug("Creating index meta......")
                await db.index_meta_collection.insert_one({"last_mongo_id": ev.ids[-1],
                                                           "last_index_id": docs[-1][0],
                                                           "backup_name": backup_name,
                                                           "modified_time": datetime.now()})
                logger.debug("Created index meta")
                
            if store_index:
                logger.debug("Storing The index to cloud........")
                await ut.store_index(backup_name)
                logger.debug("Stored index to cloud.")
            
            await cache.insert_one("last_index_id", docs[-1][0])
            logger.debug("Successfully added documents to index.")
            return StopEvent(result=(True, "Upload Successfull.", file_meta))
               
        except Exception as e:
            logger.error(f"Error in the Index update event. Error: {e.__class__.__name__} :- {str(e)}")
            return StopEvent(result=(False, f"{e.__class__.__name__} :- {str(e)}", None))




class DeleteFile(Workflow):
    """This workflow is used to delete the file from the vector database."""

    @step(num_workers=5)
    async def delete_file(self, ctx:Context, ev:StartEvent) -> StopEvent:
        """This step is used to delete the file from the vector database."""
        
        logger.info("Started deleting the file.........")  

        try:
            
            print("version ---Id : ", ev.version_id)
            assert await ut.check_realm_keys(db.user_collection, ev.uid, ev.realm, False), "realm attributes does not match or no data to process."
            
            cur_version, versions = await ut.get_doc_lt_version(db.user_collection, ev.uid, ev.realm, ev.document_id)
            
            assert cur_version != [], f"Cannot find the document with document id '{ev.document_id}'"
            
            if ev.version_id and ((ev.version_id is not None and versions) or (ev.state == "Draft" and versions)):
                
                logger.debug("Checking version creaditability........")
                
                if ev.state == "Draft":
                    ev.version_id = 0

                assert ev.version_id in versions, f"Version_id not found. Please Publish the document with the new version_id : {ev.version_id}."
                assert ev.version_id != cur_version, "Cannot delete the current latest version."
                
                if ev.version_id == 0 and ev.state != "Draft":
                    raise AssertionError(f"There is no version named {ev.version_id} in the {ev.state} document.")

                ctx.write_event_to_stream(ProgressEvent(msg="Version validation completed."))
                ctx.write_event_to_stream(ProgressEvent(msg="Deleteing data from vector store...."))
                logger.debug(f"Deleting data from vector store for uid: {ev.uid} with version: {ev.version_id}.....")

                filter = {"metadata.uid": ev.uid, "metadata.realm":ev.realm,
                          "metadata.document_id": ev.document_id, 
                          "metadata.version_id": ev.version_id, "metadata.state": ev.state,}
                
                async with asyncio.Lock():
                    
                    index = Index(
                                storage_path=os.path.join(os.getcwd(), INDEX_STORAGE_PATH),
                                cache_size=10000,
                                cache_ttl_secs=600,
                                store_positions=True,
                                in_memory=False,
                                schema=schema,
                            )
                    
                    await ut.delete_index_data(index, filter)
                    out = await db.vector_store.delete_many(filter)
                    logger.debug(f"out_results : {out}")
                    
                    __data = [i for i in index.or_query(["name"])]
                    _stat = max(__data if __data else [0])
                    logger.debug(f"data in the docs after delete : {len(__data)}")
                    logger.debug(f"The last index id: {_stat}")

                ctx.write_event_to_stream(ProgressEvent(msg="Successfully deleted data from vector store."))
                logger.debug("Successfully deleted data from vector store.")
                logger.debug("Started removing the version from user_collection.......")
                ctx.write_event_to_stream(ProgressEvent(msg="Removing the version from user_collection......."))

                data = await db.user_collection.find_one({"uid": ev.uid, "realm": ev.realm,
                                                          f"files.{ev.document_id}": {"$exists":True}})
                data["files"][ev.document_id]["versions"].remove(ev.version_id)

                if data["files"][ev.document_id]["versions"]:
                    await db.user_collection.update_one({"_id": data["_id"]},
                                                        {"$set": {f"files.{ev.document_id}.versions": data["files"][ev.document_id]["versions"]}})

                else:
                    del data["files"][ev.document_id]
                    
                    if data["files"]:
                        await db.user_collection.update_one({"_id": data["_id"]},
                                                            {"$set": {"files": data["files"]}})
                    else:
                        await db.user_collection.delete_one({"_id": data["_id"]})

                logger.info(f"Successfully removed the file version {ev.version_id} from user_collection.")
                ctx.write_event_to_stream(ProgressEvent(msg=f"Removed the file version {ev.version_id} from user_collection."))


            elif ev.version_id is None:
                
                ctx.write_event_to_stream(ProgressEvent(msg="Version validation completed."))
                ctx.write_event_to_stream(ProgressEvent(msg="Deleteing data from vector store...."))
                logger.debug(f"Deleting data from vector store for uid: {ev.uid} with version: {ev.version_id}.....")
                logger.debug(f"As version is {ev.version_id}. Removing all versions of the file.")
                ctx.write_event_to_stream(ProgressEvent(msg=f"As version is {ev.version_id}. Removing all versions of the file."))

                filter = {"metadata.uid": ev.uid, "metadata.realm": ev.realm, "metadata.document_id": ev.document_id}
                
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
                        
                        await ut.delete_index_data(index, filter)
                        await db.vector_store.delete_many(filter)
                        
                        __data = [i for i in index.or_query(["name"])]
                        _stat = max(__data if __data else [0])
                        logger.debug(f"data in the docs after delete : {len(__data)}")
                        logger.debug(f"The last index id: {_stat}")
                    
                except Exception:
                    pass
                
                ctx.write_event_to_stream(ProgressEvent(msg="Successfully deleted data from vector store."))
                logger.debug("Successfully deleted data from vector store.")
                logger.debug("Started removing the file from user_collection......")
                ctx.write_event_to_stream(ProgressEvent(msg="Removing the version from user_collection......."))

                data = await db.user_collection.find_one({"uid": ev.uid, "realm": ev.realm,
                                                          f"files.{ev.document_id}": {"$exists": True}})
                del data["files"][ev.document_id]
                
                if data["files"]:
                    await db.user_collection.update_one({"_id": data["_id"]},
                                                        {"$set": {"files" : data["files"]}})
                else:
                    await db.user_collection.delete_one({"_id": data["_id"]})

                logger.debug("Successfully removed the file from user_collection.")
                ctx.write_event_to_stream(ProgressEvent(msg="Removed the file from user_collection."))
                
            elif not versions:
                
                ctx.write_event_to_stream(ProgressEvent(msg="Skipping deletion of data from vector store as it is empty."))
                logger.debug(f"Skipping deletion of data from vector store for uid: {ev.uid} with version: {ev.version_id} as it is empty.")
                logger.debug("Started removing the file from user_collection......")
                ctx.write_event_to_stream(ProgressEvent(msg="Removing the version from user_collection......."))
                
                data = await db.user_collection.find_one({"uid": ev.uid, "realm": ev.realm,
                                                          f"files.{ev.document_id}": {"$exists":True}})
                del data["files"][ev.document_id]
                
                if data["files"]:
                    await db.user_collection.update_one({"_id":data["_id"]},
                                                        {"$set": {"files" : data["files"]}})
                else:
                    await db.user_collection.delete_one({"_id":data["_id"]})
                    
                logger.debug("Successfully removed the file from user_collection.") 
                ctx.write_event_to_stream(ProgressEvent(msg="Removed the file from user_collection."))

            logger.info("Completed deleting the file.")
            ctx.write_event_to_stream(ProgressEvent(msg="Completed deleting the file."))
            
            try:
                await cache.delete_one(ev.uid)
            except Exception as e:
                logger.warning(f"Failed to delete cache for uid: {ev.uid}. Error: {e}")
            
            return StopEvent(result=(True, "File deleted successfully."))

        except Exception as e:
            logger.error(f"Error in deleting the file. Error: {e.__class__.__name__} :- {str(e)}")
            return StopEvent(result=(False, f"{e.__class__.__name__} :- {str(e)}"))
