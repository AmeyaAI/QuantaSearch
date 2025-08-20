###

async def get_insertable_data_pipeline(uid:str, realm:dict):
    
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