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