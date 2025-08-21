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
    Creates pipeline to identify user collection documents that have less than 50 files,
    allowing for additional file insertions without exceeding collection limits.
    
    Args:
        uid (str): User identifier
        realm (dict): Realm filter parameters for data isolation
        
    Returns:
        list[dict]: MongoDB aggregation pipeline stages for finding insertable documents
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