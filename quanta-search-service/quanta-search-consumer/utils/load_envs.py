import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
 
load_dotenv(override=True, dotenv_path=f"{os.path.split(__file__)[0]}/../.env")

os.environ["LOAD_EASYOCR"] = "true"

class ENV(BaseSettings):

    RABBIT_HOST:str = os.getenv("RABBIT_HOST", "quanta_search_rabbitmq")
    RABBIT_PORT:int = int(os.getenv("RABBIT_PORT", 5672)) or 5672
    
    REDIS_HOST:str = os.getenv("REDIS_HOST", "quanta_search_redis")
    REDIS_PORT:int = int(os.getenv("REDIS_PORT", 6379)) or 6379
    
    MONGODB_URI:str = os.getenv("MONGODB_URI")
    MONGO_VDB_NAME:str = os.getenv("MONGO_VDB_NAME", "File_search_VB")
    MONGO_VDB_COLLECTION_NAME:str = os.getenv("MONGO_VDB_COLLECTION_NAME", "File_search_VB_Index")
    MONGO_DB_USER_COLLECTION_NAME: str = os.getenv("MONGO_DB_USER_COLLECTION_NAME", "File_search_user")
    MONGODB_INDEX_META_COLLECTION_NAME: str = os.getenv("MONGODB_INDEX_META_COLLECTION_NAME", "Index_meta")
    
    LAST_INDEX_NUM:int = int(os.getenv("LAST_INDEX_NUM", 1)) or 1
    INDEX_BACKUP_MAX_SIZE:int = int(os.getenv("INDEX_BACKUP_MAX_SIZE", 52428800)) or 52428800
    INDEX_BACKUP_NAME:str = os.getenv("INDEX_BACKUP_NAME", "Index_backup_1")
    INVERTED_INDEX_PATH:str = os.getenv("INVERTED_INDEX_PATH", "ameya-inverted-index/fast-index-storage")
    
    EASYOCR_DEVICE:str = os.getenv("EASYOCR_DEVICE", "cpu")
        
env = ENV()