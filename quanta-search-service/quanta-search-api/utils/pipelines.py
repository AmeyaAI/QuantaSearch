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


from utils.load_envs import env

async def load_get_list_pipeline(uid: str) -> list[dict]:

    return [
                {
                    "$match": {
                    "uid": uid
                    }
                },
                {
                    "$project": {
                    "fileIds": { "$objectToArray": "$files" }
                    }
                },
                {
                    "$unwind": "$fileIds"
                },
                {
                    "$lookup": {
                    "from": env.MONGO_VDB_COLLECTION_NAME,
                    "let": { "doc_id": "$fileIds.k" },
                    "pipeline": [
                        {
                        "$match": {
                            "$expr": {
                            "$eq": ["$metadata.document_id", "$$doc_id"]
                            }
                        }
                        },
                        {"$limit": 1}
                    ],
                    "as": "vectorData"
                    }
                },
                {
                    "$match": {
                    "vectorData": { "$ne": [] }
                    }
                },
                {
                    "$project": {
                    "_id": 0,
                    "file_name": { "$arrayElemAt": ["$vectorData.metadata.file_name", 0] },
                    "uploaded_date": { "$arrayElemAt": ["$vectorData.metadata.uploaded_date", 0] },
                    "published_date": { "$arrayElemAt": ["$vectorData.metadata.published_date", 0] },
                    "version_change_date": { "$arrayElemAt": ["$vectorData.metadata.version_change_date", 0] },
                    "file_id": "$fileIds.k",
                    "versions": "$fileIds.v.versions",
                    "current_version": "$fileIds.v.current_version"
                    }
                }
            ]
    
    
    
async def load_vector_pipeline(vectotr_index_name:str, query_embed:list[float], filters:tuple, top_k:int,
                               threshold:float) -> list[dict]:
    return [
                {
                    "$vectorSearch": {
                        "index": vectotr_index_name,
                        "path" : "embedding",
                        "filter": {"$and": filters[0]},
                        "queryVector" : query_embed,
                        "numCandidates": 100,
                        "limit": top_k,                        
                    }
                },
                {"$addFields": {"score": {'$meta': 'vectorSearchScore'}}},
                {"$match": filters[1]},
                {"$match": {
                    "score": {"$gte": threshold}
                    }
                },
                {"$addFields": {
                        "adjusted_score": {
                            "$round": [{"$multiply": ["$score", 100]}, 3]
                        }
                    }
                },
                {"$group": {
                    "_id": "$metadata.file_name",
                    "highestScore": {"$max": "$adjusted_score"},
                    "document": {"$first": "$$ROOT"}
                    }
                },
                {"$replaceRoot": {"newRoot": "$document"}},
                {"$sort": {"adjusted_score": -1}},
                {"$project": {"realm": "$metadata.realm",
                              "user_id": "$metadata.user_id",
                              "version_id": "$metadata.version_id",
                              "document_name": "$metadata.file_name",
                              "document_id": "$metadata.document_id",
                              "uploaded_date": "$metadata.uploaded_date",
                              "published_date": "$metadata.published_date",
                              "version_change_date": "$metadata.version_change_date",
                              "relavence_score": "$adjusted_score", "_id": 0}}
            ]
    

async def load_search_pipeline(search_index_name:str, query:str, filters:tuple, top_k:int,
                               threshold:float, weightage:float=0.4) -> list[dict]:
    return [{
                "$search" : {
                    "index" : search_index_name,
                    "compound": {
                        "filter": filters,
                        "must": [{"text" : {"query" : query, "path" : "text"}}] 
                        }
                }
            },
            {"$addFields": {"score": {"$meta": "searchScore"}}},
            {"$sort": {"score": -1}},
            {"$group": {
                        "_id": "$metadata.file_name",
                        "document": {"$first": "$$ROOT"}
                    }
                },
            {"$replaceRoot": {"newRoot": "$document"}},
            {"$limit": 200},
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
            {"$match": {
                "sigmoidScore": {"$gte": threshold}
                }
            },
            {"$addFields": {
                    "adjusted_score": {
                        "$round": [{"$multiply": ["$sigmoidScore", 1, 100]}, 3]
                    }
                }
            },
            {"$project": {"realm": "$metadata.realm",
                          "user_id": "$metadata.user_id",
                          "version_id": "$metadata.version_id",
                          "document_name": "$metadata.file_name",
                          "document_id": "$metadata.document_id",
                          "uploaded_date": "$metadata.uploaded_date",
                          "published_date": "$metadata.published_date",
                          "version_change_date": "$metadata.version_change_date",
                          "relavence_score": "$adjusted_score", "_id": 0, "text":1}}
            ]
    

async def load_text_search_pipeline(query:str, filters:dict, top_k:int, threshold:float, weightage:float=0.4) -> list[dict]:
    ftls = filters.copy()
    ftls.update({"$text": {"$search": "\""+ query +"\""}})
    
    return [{
                "$match": ftls
            },
            {"$addFields": {"scoreint": {"$meta": "textScore"}}},
            {"$addFields": {"score": {"$multiply": [3, "$scoreint"]}}},
            {"$sort": {"score": -1}},
            {"$group": {
                        "_id": "$metadata.file_name",
                        "document": {"$first": "$$ROOT"}
                    }
                },
            {"$replaceRoot": {"newRoot": "$document"}},
            {"$limit": 200},
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
            {"$match": {
                        "score": {"$gte": threshold}
                    }
            },
            {"$addFields": {
                    "adjusted_score": {
                        "$round": [{"$multiply": ["$sigmoidScore", weightage, 100]}, 3]
                    }
                }
            },
            {"$project": {"realm": "$metadata.realm",
                          "user_id": "$metadata.user_id",
                          "version_id": "$metadata.version_id",
                          "document_name": "$metadata.file_name",
                          "document_id": "$metadata.document_id",
                          "uploaded_date": "$metadata.uploaded_date",
                          "published_date": "$metadata.published_date",
                          "version_change_date": "$metadata.version_change_date",
                          "relavence_score": "$sigmoidScore", "_id": 0, "text":1}}
        ]
    
    
async def load_document_count_pipeline(uid:str):
    return [
        {
            "$match": { "uid": uid }
        },
        {
            "$project": {
            "r_keys": 1,
            "file_versions_count": {
                "$sum": {
                "$map": {
                    "input": { "$objectToArray": "$files" },
                    "as": "file",
                    "in": { "$size": "$$file.v.versions" }
                }
                }
            }
            }
        },
        {
            "$unwind": {"path": "$r_keys",
                        "preserveNullAndEmptyArrays": True}
        },
        {
            "$group": {
            "_id": "$r_keys",
            "document_count": { "$sum": "$file_versions_count" }
            }
        },
        {
            "$project": {
            "r_key": "$_id",
            "document_count": 1,
            "_id": 0
            }
        }
    ]
>>>>>>> c1e0d3d (Added copyright text on each source files)


async def get_insertable_data_pipeline(uid:str, realm:dict) -> list[dict]:
    """
    Creates pipeline to find user collection documents that have
    less than 50 files (space for more insertions).
    
    Args:
        uid (str): User identifier
        realm (dict): Realm filter parameters
        
    Returns:
        list[dict]: MongoDB aggregation pipeline stages
    """
    
    return [
            {
                "$match": {
                    "uid": uid, 
                    "realm": realm,
                    "$expr": {
                        "$lt": [{ "$size": { "$objectToArray": "$files" } }, 50]
                    }
                }
            },
            {
                "$project": {
                    "_id": 1
                }
            },
            {
                "$limit": 1
            }
        ]
    

async def get_list_files_pipeline(filters:dict) -> list[dict]:
    """
    Creates pipeline to extract and format file information
    from user collection documents.
    
    Args:
        filters (dict): Filter conditions for user documents
        
    Returns:
        list[dict]: MongoDB aggregation pipeline stages
    """
    
    return [
            {"$match": filters},
            {
                "$project": {
                    "documents": {"$objectToArray": "$files"},
                    "realm": 1
                }
            },
            {"$unwind": "$documents"},
            {"$project": 
                {
                    "_id": 0,
                    "file_name":"$documents.v.file_name",
                    "uploaded_date": "$documents.v.uploaded_date",
                    "published_date": "$documents.v.published_date",
                    "version_change_date": "$documents.v.version_change_date",
                    "document_id": "$documents.k",
                    "realm": "$realm",
                    "versions": "$documents.v.versions",
                    "status": "$documents.v.status",
                    "current_version": "$documents.v.current_version"
                    }
            }
    ]