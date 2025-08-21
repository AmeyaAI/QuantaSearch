###

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