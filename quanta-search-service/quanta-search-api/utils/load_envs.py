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
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
 
load_dotenv(override=True, dotenv_path=f"{os.path.split(__file__)[0]}/../.env")

class ENV(BaseSettings):

    RABBIT_HOST:str = os.getenv("RABBIT_HOST", "quanta_search_rabbitmq")
    RABBIT_PORT:int = int(os.getenv("RABBIT_PORT", 5672)) or 5672
    
    REDIS_HOST:str = os.getenv("REDIS_HOST", "quanta_search_redis")
    REDIS_PORT:int = int(os.getenv("REDIS_PORT", 6379)) or 6379

    LAST_INDEX_NUM:int = int(os.getenv("LAST_INDEX_NUM", 1)) or 1
    MAX_SCORE:float = float(os.getenv("MAX_SCORE", 0.99998)) or 0.99998
    BASE_SCORE:float = float(os.getenv("BASE_SCORE", 0.7)) or 0.7
    MAX_DOC_LIMIT: int = int(os.getenv("MAX_DOC_LIMIT", 200)) or 200
    PREVIEW_LENGTH:int = int(os.getenv("PREVIEW_LENGTH", 3)) or 3
    PREVIEW_DIVISOR:int = int(os.getenv("PREVIEW_DIVISOR", 10)) or 10
    MAX_PREVIEW_COUNT:int = int(os.getenv("MAX_PREVIEW_COUNT", 3)) or 3
    BASE_PREVIEW_SCORE:float = float(os.getenv("BASE_PREVIEW_SCORE", 0.9)) or 0.9
    RETRIVER_CUT_OFF_THRESH:float = float(os.getenv("RETRIVER_CUT_OFF_THRESH", 0.655)) or 0.655
    
    MONGODB_URI:str = os.getenv("MONGODB_URI")
    MONGO_VDB_NAME:str = os.getenv("MONGO_VDB_NAME", "File_search_VB")
    MONGO_VDB_COLLECTION_NAME:str = os.getenv("MONGO_VDB_COLLECTION_NAME", "File_search_VB_Index")
    MONGO_DB_USER_COLLECTION_NAME: str = os.getenv("MONGO_DB_USER_COLLECTION_NAME", "File_search_user")
    MONGODB_INDEX_META_COLLECTION_NAME: str = os.getenv("MONGODB_INDEX_META_COLLECTION_NAME", "Index_meta")
    
    INVERTED_INDEX_PATH:str = os.getenv("INVERTED_INDEX_PATH", "ameya-inverted-index/fast-index-storage")

    REALM_KEYS:str = os.getenv("REALM_KEYS", "")
    REALM_CONFIG_JSON_PATH:str = os.getenv("REALM_CONFIG_JSON_PATH", "")
  
env = ENV()