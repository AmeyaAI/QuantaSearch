import asyncio
from fast_inverted_index import Index, PyQueryNode, PyQueryExecutionParams

from db.db import db
from utils.load_envs import env
from logger.logger import logger


base_score = env.BASE_SCORE
lock = asyncio.Lock()

async def index_retriver(index:Index, query:str, search_type:str) -> list:
    """
    Retrieve document IDs from the inverted index using different search strategies.
    
    Args:
        index (Index): Fast inverted index instance
        query (str): Search query string
        search_type (str): Type of search - 'text_search', 'search', or 'sp_search'
        
    Returns:
        list: List of document titles matching the search criteria
    """
    
    if search_type == "text_search":
        
        logger.debug("Performing text search.........")
        _query = PyQueryNode.phrase("content", query.split())
        params = PyQueryExecutionParams(
            scoring_algorithm="bm25l")
        
        async with lock:
            data = index.execute_query(_query, params)
            logger.debug(f"Total files filtered for text_search : {data.len()}")
            out = [index.get_document(i[0])["title"] for i in data.scored_docs]
        
        logger.debug("Completed text search.")
            
    elif search_type == "search":
        logger.debug("Performing search.........")
        
        async with lock:
            data = index.and_query(query.split())
            logger.debug(f"Total files filtered for search : {len(data)}")
            out = [index.get_document(i)["title"] for i in data]
        
        logger.debug("Completed search.")
             
    elif search_type == "sp_search":
        logger.debug("Performing space search.........")
        
        async with lock:
            data = index.or_query(query.split())
            logger.debug(f"Total files filtered for space search : {len(data)}")
            out = [index.get_document(i)["title"] for i in data]
        
        logger.debug("Completed space search.")
    
    print(f"len of out data for {search_type} : {len(out)}")
    return out
        


async def fetch_docs_optimized(doc_ids: list, filters: dict, query:str, batch_size: int = 5000,
                               max_concurrency: int = 10, search:bool=False):
    """
    Highly optimized version that minimizes database roundtrips to fetch documents.
    
    Args:
        doc_ids (list): List of document IDs to fetch
        filters (dict): Database filters to apply
        query (str): Search query for text search operations
        batch_size (int, optional): Size of batches for processing. Defaults to 5000
        max_concurrency (int, optional): Maximum concurrent operations. Defaults to 10
        search (bool, optional): Whether to use text search scoring. Defaults to False
        
    Returns:
        list: List of document data with relevance scores and metadata
    """
    
    if not doc_ids and not search:
        return []
    
    unique_ids = doc_ids
    
    projection = {
            "_id": 1, "text": 1,
            "realm": "$metadata.realm",
            "user_id": "$metadata.user_id",
            "version_id": "$metadata.version_id", 
            "document_name": "$metadata.file_name",
            "document_id": "$metadata.document_id",
            "uploaded_date": "$metadata.uploaded_date",
            "published_date": "$metadata.published_date",
            "version_change_date": "$metadata.version_change_date"
        }
    
    if len(unique_ids) <= batch_size:
        
        if search:
            flt={}
            flt.update(filters[0])
            flt.update({"$text": {"$search": "\""+ query +"\""}})
            
            logger.debug("Using text search pipeline in single mode....")
            
            pipeline = [{"$match": flt},
                        {"$match": filters[1]},
                        {"$addFields": {"scoreint": {"$meta": "textScore"}}},
                        {"$addFields": {"score": {"$multiply": [3, "$scoreint"]}}},
                        {"$sort": {"score": -1}},
                        {"$group": {
                                "_id": "$metadata.file_name",
                                "document": {"$first": "$$ROOT"}
                            }
                        },
                        {"$replaceRoot": {"newRoot": "$document"}},
                        {"$addFields": {"sigmoidScore": {
                                            "$divide": [
                                                1, {"$add": [
                                                        1, {"$exp": {"$multiply": [-1, "$score"]}}
                                                    ]
                                                }
                                            ]
                                        }
                                    }
                        },
                        {"$match": {"score": {"$gte": env.RETRIVER_CUT_OFF_THRESH}}},
                        {"$project": {"realm": "$metadata.realm",
                          "user_id": "$metadata.user_id",
                          "version_id": "$metadata.version_id",
                          "document_name": "$metadata.file_name",
                          "document_id": "$metadata.document_id",
                          "uploaded_date": "$metadata.uploaded_date",
                          "published_date": "$metadata.published_date",
                          "version_change_date": "$metadata.version_change_date",
                          "relavence_score":"$sigmoidScore", "_id": 0, "text":1}}
                    ]
        else:
            logger.debug(f"got on single else part")
            logger.debug(f"the filters are : {filters}")
            flt = {"_id": {"$in": unique_ids}}
            flt.update(filters)
            
            pipeline = [{"$match": flt},
                        {"$group": {
                                "_id": "$metadata.file_name",
                                "document": {"$first": "$$ROOT"}
                            }
                        },
                        {"$replaceRoot": {"newRoot": "$document"}},
                        {"$project": projection}
                    ]

        cursor = await db.vector_store.aggregate(pipeline=pipeline, allowDiskUse=True, batchSize=batch_size)
        
        docs = []
        async for doc in cursor:
            if not search:
                doc["relavence_score"] = base_score
            docs.append(doc)
            
        logger.debug(f"Single query fetched {len(docs)} documents")
        return docs
    
    
    chunks = [unique_ids[i:i + batch_size] for i in range(0, len(unique_ids), batch_size)]
    semaphore = asyncio.Semaphore(max_concurrency)
    
    async def fetch_chunk_optimized(chunk, semaphore, search):
        async with semaphore:
            if search:
                flt={}
                flt.update(filters[0])
                flt.update({"$text": {"$search": "\""+ query +"\""}})
                
                pipeline = [{"$match": flt},
                            {"$match": filters[1]},
                            {"$addFields": {"scoreint": {"$meta": "textScore"}}},
                            {"$addFields": {"score": {"$multiply": [3, "$scoreint"]}}},
                            {"$sort": {"score": -1}},
                            {"$group": {
                                    "_id": "$metadata.file_name",
                                    "document": {"$first": "$$ROOT"}
                                }
                            },
                            {"$replaceRoot": {"newRoot": "$document"}},
                            {"$addFields": {"sigmoidScore": {
                                                "$divide": [
                                                    1, {"$add": [
                                                            1, {"$exp": {"$multiply": [-1, "$score"]}}
                                                        ]
                                                    }
                                                ]
                                            }
                                        }
                            },
                            {"$match": {"score": {"$gte": env.RETRIVER_CUT_OFF_THRESH}}},
                            {"$project": {"realm": "$metadata.realm",
                            "user_id": "$metadata.user_id",
                            "version_id": "$metadata.version_id",
                            "document_name": "$metadata.file_name",
                            "document_id": "$metadata.document_id",
                            "uploaded_date": "$metadata.uploaded_date",
                            "published_date": "$metadata.published_date",
                            "version_change_date": "$metadata.version_change_date",
                            "relavence_score":"$sigmoidScore", "_id": 0, "text":1}}
                        ]
            else:
                flt = {"_id": {"$in": chunk}}
                flt.update(filters)
                
                pipeline = [{"$match": flt},
                            {"$group": {
                                    "_id": "$metadata.file_name",
                                    "document": {"$first": "$$ROOT"}
                                }
                            },
                            {"$replaceRoot": {"newRoot": "$document"}},
                            {"$project": projection}
                        ]
            
            cursor = await db.vector_store.aggregate(pipeline, allowDiskUse=True, batchSize=int(batch_size/5))
            
            docs = []
            async for doc in cursor:
                if not search:
                    doc["relavence_score"] = base_score
                docs.append(doc)
            
            logger.debug(f"finished chunk size : {len(chunk)}")
            return docs

    tasks = [fetch_chunk_optimized(chunk, semaphore, search) for chunk in chunks]
    chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    results = []
    for chunk_result in chunk_results:
        if not isinstance(chunk_result, Exception):
            results.extend(chunk_result)
            
        else:
            raise chunk_result

    f_out = results
        
    logger.debug(f"Optimized fetch completed: {len(f_out)} documents")
    return f_out