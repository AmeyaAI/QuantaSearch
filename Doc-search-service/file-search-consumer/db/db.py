import logging
from threading import Lock

from pymongo import AsyncMongoClient
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure

from utils.load_envs import env


dev_url = env.MONGODB_URI
logging.getLogger("pymongo").setLevel(logging.WARNING)
logging.getLogger("motor").setLevel(logging.WARNING)


class Database:
    _instance = None
    _lock = Lock()
    

    def __new__(cls):

        try:

            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.client = AsyncMongoClient(dev_url, serverSelectionTimeoutMS=10000)
                    cls._instance.db = cls._instance.client[env.MONGO_VDB_NAME]

                    cls.vector_store = cls._instance.db[env.MONGO_VDB_COLLECTION_NAME]
                    cls.user_collection = cls._instance.db[env.MONGO_DB_USER_COLLECTION_NAME]
                    cls.index_meta_collection = cls._instance.db[env.MONGODB_INDEX_META_COLLECTION_NAME]

                return cls._instance

        except (ServerSelectionTimeoutError, ConnectionFailure) as e:
            raise e

    @classmethod
    async def connection_check(cls):
        try:
            if cls._instance:
                cls._instance.client.admin.command('ismaster')
                return "Connection Established from MongoDB"

            else:
                raise ConnectionFailure("Cant to connect MongoDB")

        except (ServerSelectionTimeoutError, ConnectionFailure) as e:
            raise e


db = Database()