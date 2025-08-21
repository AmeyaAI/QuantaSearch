from pymongo.operations import SearchIndexModel

from db.db import db
from logger.logger import logger


async def create_mongodb_atlas_indexes(dim:int = 768):
    """
    Create MongoDB Atlas search indexes including vector search, full-text search, and spatial indexes.
    
    Args:
        dim (int, optional): Vector embedding dimensions. Defaults to 768
        
    Returns:
        bool: True if all indexes were created successfully
    """

    collection = db.vector_store
    user_collection = db.user_collection

    vs_model = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": dim,
                    "similarity": "cosine",
                },
                
                {"type": "filter", "path": "metadata.uid"},
                {"type": "filter", "path": "metadata.state"},
            ]
        },
        name="vector_index",
        type="vectorSearch",
    )

    fts_model = SearchIndexModel(
        definition={"mappings": {"dynamic": False, "fields": {"text": {"type": "string"},
                                                             "metadata": {"type": "document",
                                                                          "fields": {"uid": {"type": "token"},
                                                                                    "state": {"type": "token"},
                                                                                    "document_id": {"type": "token"},
                                                                                    "version_id": {"type": "token"},
                                                                                    "realm": {"dynamic": True, 
                                                                                              "type": "document",
                                                                                              "fields": {"$**":{"type": "token"}}}
                                                                                    }
                                                                    }
                                                             }
                                 }
                    },
        name="fts_index",
        type="search",
    )
    
    sp_model = SearchIndexModel(
        definition={"mappings": {"dynamic": False, "fields": {"text": {"type": "string", "analyzer": "lucene.whitespace"},
                                                             "metadata": {"type": "document",
                                                                          "fields": {"uid": {"type": "token"},
                                                                                    "state": {"type": "token"},
                                                                                    "document_id": {"type": "token"},
                                                                                    "version_id": {"type": "token"},
                                                                                    "realm": {"dynamic": True, 
                                                                                              "type": "document",
                                                                                              "fields": {"$**":{"type": "token"}}}
                                                                                    }
                                                                    }
                                                             }
                                 }
                    },
        name="sp_index",
        type="search",
    )

    avail_index= [i["name"] async for i in await collection.list_search_indexes()]
    
    await collection.create_index({"metadata.uid": 1, "metadata.realm": 1,
                                   "metadata.document_id": 1, "metadata.version_id": 1,
                                   "metadata.state": 1})
    
    await collection.create_index({"metadata.uid": 1, "metadata.state": 1, "metadata.document_id": 1,
                                   "metadata.realm.$**": 1})

    await collection.create_index({"metadata.uid": 1, "metadata.state":1,
                                   "text":"text"})
    
    await collection.create_index({"metadata.uid": 1, "metadata.document_id": 1,
                                   "metadata.realm.$**": 1})
    
    await collection.create_index({"_id":1, "metadata.uid": 1, "metadata.state":1,
                                   "metadata.realm.$**":1})
    
    await collection.create_index({"metadata.uid": 1, "metadata.state":1,
                                   "metadata.realm.$**":1})
    
    await collection.create_index({"metadata.realm.$**": 1})
    
    await user_collection.create_index({"uid": 1})
    await user_collection.create_index({"realm": 1})
    
    await user_collection.create_index({"uid": 1, "realm": 1})
    await user_collection.create_index({"uid":1, "realm.$**":1})

    for model in [vs_model, fts_model, sp_model]:

        logger.debug(f"Creating index for model '{model.document['name']}'")

        if model.document["name"] in avail_index:
            logger.warning(f"Duplicate index found for model '{model.document['name']}'. Skipping index creation.")

        else:
            
            await collection.create_search_index(model=model)
            logger.debug(f"Created index for model '{model.document['name']}'")

    logger.info("MongoDB indexes created successfully")

    return True