import os
import sys
import json
import logging
import asyncio
import aio_pika
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from db.db import db
from utils.load_envs import env
from logger.logger import logger
from llama_index.core.workflow import StopEvent
from schemas.schema import ProgressEvent
from core.file_upload import FileSearcherUpload, DeleteFile



logging.getLogger("aiormq.connection").setLevel(logging.WARNING)
logging.getLogger("aio_pika.robust_connection").setLevel(logging.WARNING)
logging.getLogger("logger.logger").setLevel(logging.DEBUG)



class RabbitMQConsumer:
    def __init__(self, ds_upload_timeout=3600.0):
        self.upload_obj = FileSearcherUpload(timeout=ds_upload_timeout)
        self.delete_obj = DeleteFile(timeout=ds_upload_timeout/10)
        self.connection = None
        self.channel = None
        self.process_is_consuming = False
        self.delete_is_consuming = False
        self.semaphore = asyncio.Semaphore(2)

    async def connect(self):
        """Establish a connection to RabbitMQ with robust error handling."""
        while True:
            try:
                logger.info("Attempting to connect to RabbitMQ")
                self.connection = await aio_pika.connect_robust(
                    host=env.RABBIT_HOST,
                    port=int(env.RABBIT_PORT),
                    heartbeat=600,
                    connection_attempts=5,
                    retry_delay=0.5,
                )
                
                logger.info("Successfully connected to RabbitMQ")
                return self.connection
            
            except (aio_pika.exceptions.AMQPConnectionError, ConnectionError) as e:
                logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
                await asyncio.sleep(5)


    async def process_message(self, message: aio_pika.IncomingMessage):
        async with message.process():
            common_datas = json.loads(message.body.decode('utf-8'))
            logger.info(f"Received message: {common_datas}")
            
            state = common_datas.get("state",None)
            status,error = "fail","un-known error"
            path = ""
            st = time.perf_counter()
            
            try:
                async with self.semaphore:
                    if state and state.lower() == "draft":
                        path = "/function/managedocuments/adddraftdocument/event/documentsearch_draft_upload"
                        status,error = await draft_function(obj = self.upload_obj,status=status,error=error,common_datas = common_datas)   

                    elif state and state.lower() == "publish":
                        path ="/function/managedocuments/addpublisheddocument/event/documentsearch_publish_upload"
                        status,error = await publish_function(obj = self.upload_obj,status=status,error=error,common_datas = common_datas)

                    else :
                        error = "state not found"


            except Exception as e:
                error = str(e)
                logger.error(f"Unexpected error in message processing: {e}")

    
    async def delete_process(self, message: aio_pika.IncomingMessage):
        async with message.process():
            common_datas = json.loads(message.body.decode('utf-8'))
            logger.info(f"Received delete message: {common_datas}")
            uid = common_datas.get("uid")
            realm = common_datas.get("realm")
            document_id = common_datas.get("document_id")
            version_id = common_datas.get("version_id")
            state = common_datas.get("state")
            reply_to = common_datas.get("reply")
            correlation_id = common_datas.get("correlation_id")
            
            channel = None
            try:
                channel = await self.connection.channel()
                
                handler = self.delete_obj.run(
                                                uid = uid,
                                                realm = realm,
                                                document_id = document_id,
                                                version_id = version_id,
                                                state = state
                                            )
                
                async for event in handler.stream_events():
                    
                    if isinstance(event, StopEvent):
                        if not event.result[0]:
                            logger.debug(f"Stop_response : {event.result}")
                            raise Exception(event.result[1])
                        break

                    if isinstance(event, ProgressEvent):
                        event_type = "progress"
                        response = {
                            "type": event_type,
                            "data": {"msg": event.msg, "done": False},
                        }
                        logger.debug(f"Progress_response : {response}")
                        
                        await channel.default_exchange.publish(
                                    aio_pika.Message(
                                        body=json.dumps(response).encode(),
                                        correlation_id=correlation_id,
                                        priority=10,
                                        headers={"event_type": event_type},
                                    ),
                                    routing_key=reply_to,
                                )

                result = await handler

                done_response = {"type": "progress", "data": {"msg": "", "done": True}}
                logger.debug(f"Progress_response : {done_response}")
                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=json.dumps(done_response).encode(),
                        correlation_id=correlation_id,
                        priority=10,
                    ),
                    routing_key=reply_to,
                )
            
            except Exception as e:
                error_response = {"type": "error", "data": {"msg": str(e), "done": True}}
                
                logger.error(f"Error_response : {error_response}")
                print("error : _--------> " ,error_response)
                
                if channel is None:
                    channel = await self.connection.channel()
                    
                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=json.dumps(error_response).encode(),
                        correlation_id=correlation_id,
                        priority=10,
                    ),
                    routing_key=reply_to,
                )
            
            finally:
                if channel:
                    await channel.close()


    async def start_consuming(self):
        while True:
            try:
                self.connection = await self.connect()
                
                self.channel = await self.connection.channel()
                await self.channel.set_qos(prefetch_count=1)
                
                exchange = await self.channel.declare_exchange('topic', aio_pika.ExchangeType.TOPIC)
                queue = await self.channel.declare_queue('production_docsearch_files_consumer', exclusive=False)
                await queue.bind(exchange, routing_key="doc_search_files.*")
                
                self.delete_exchange = await self.channel.declare_exchange('delete', aio_pika.ExchangeType.TOPIC)
                delete_queue = await self.channel.declare_queue('production_docsearch_delete_consumer', exclusive=False)
                await delete_queue.bind(self.delete_exchange, routing_key="doc_search_delete.*")

                logger.info("Starting to consume messages from RabbitMQ for Upload Process")
                print("Starting to consume messages from RabbitMQ for Upload Process")
                self.process_is_consuming = True
                await queue.consume(self.process_message, no_ack=False)
                
                logger.info("Starting to consume messages from RabbitMQ for Delete Process")
                print("Starting to consume messages from RabbitMQ for Delete Process")
                self.delete_is_consuming = True
                await delete_queue.consume(self.delete_process, no_ack=False)

                await asyncio.Future()

            except Exception as e:
                logger.error(f"Error in consumption loop: {e}")
                self.is_consuming = False
                
                await asyncio.sleep(5)





async def draft_function(obj,common_datas:dict, status:str="success", error:str="none"):
    uid = common_datas.get("uid",None)
    realm = common_datas.get("realm",{})
    user_id = common_datas.get("user_id",None)
    s3_file_path = common_datas.get("s3_file_path",None)
    version_id = common_datas.get("version_id",None)
    document_ids = common_datas.get("document_ids",None)
    uploaded_date = common_datas.get("uploaded_date",None)
    event_id = common_datas.get("event_id",None)
    parser_type = common_datas.get("parse_type", "docling")
    extraction_mode = common_datas.get("extraction_mode", "default")
    file_names = common_datas.get("file_names",None)

    
    try:
        st = time.time()
        ret, result, f_meta = await obj.run(
                uid = uid,
                realm = realm,
                user_id = user_id,
                s3_file_path = s3_file_path.copy(),
                version_id = version_id,
                document_id = document_ids.copy(),
                uploaded_date = uploaded_date,
                parser_type=parser_type,
                parser_mode=extraction_mode,
                event_id=event_id,
                state = "Draft"
            )

        ed = time.time()
        if ret:
            logger.debug("Successfully completed draft upload event run.")
            logger.info(f"time-taken to run the upload draft : {ed - st} seconds.")
            
            logger.debug(f"the data of f_meta : {f_meta}")
            
            if isinstance(f_meta, dict):
                logger.debug("the return instance is dict")
                for i, j in zip(document_ids, file_names):
                    if f_meta[j]["status"] == "Success":
                        logger.debug(f"Updating doc_id : {i}")
                        up__dat_d = await db.user_collection.update_many({"uid":uid, "realm":realm,
                                                                         f"files.{i}": {"$exists": True}},
                                                            {"$set": {f"files.{i}.status": f_meta[j]["status"]}})
                        logger.debug(f"The results for that update : {up__dat_d}")
                    else:
                        logger.debug(f"Updating doc_id : {i}")
                        up__dat_f = await db.user_collection.update_many({"uid": uid, "realm": realm,
                                                                         f"files.{i}": {"$exists": True}},
                                                            {"$set": {f"files.{i}.status": "Failed"}})
                        logger.debug(f"The results for that update : {up__dat_f}")
            
            elif isinstance(f_meta, list):
                logger.debug("the return instance is list")
                for i in document_ids:
                    logger.debug(f"Updating doc_id : {i}")
                    up_dat = await db.user_collection.update_many({"uid":uid, "realm":realm,
                                                                  f"files.{i}": {"$exists": True}},
                                                        {"$set": {f"files.{i}.status": "Success"}})
                    logger.debug(f"The results for that update : {up_dat}")
                
            return status, error
            
            
        elif not ret and result == "AssertionError :- realm attributes does not match or no data to process.":
            logger.debug(f"Error triggered")           
            raise Exception("AssertionError :- realm attributes does not match or no data to process.")
        
        else:
            logger.debug(f"Error triggered") 
            raise Exception(str(result))

    except Exception as e:
        status = "fail"
        error = str(e)
    
        logger.error(f"the error is : {error}")
        logger.error(f"Initiated the error in the draft consume process for uid : {uid}")
        
        
        for i in document_ids:
            logger.debug(f"Updating doc_id : {i}")
            f_d = await db.user_collection.update_many({"uid": uid, "realm": realm,
                                                       f"files.{i}": {"$exists": True}},
                                                {"$set": {f"files.{i}.status": "Failed"}})
            logger.debug(f"The results for that update : {f_d}")
        
        return status,error

async def publish_function(obj, common_datas:dict, status:str="success", error:str="none"):
    uid = common_datas.get("uid",None)
    realm = common_datas.get("realm",{})
    user_id = common_datas.get("user_id",None)
    s3_file_path = common_datas.get("s3_file_path",None)
    version_id = common_datas.get("version_id",None)
    document_ids = common_datas.get("document_ids",None)
    published_date = common_datas.get("published_date",None)
    event_id = common_datas.get("event_id",None)
    parser_type = common_datas.get("parse_type", "docling")
    extraction_mode = common_datas.get("extraction_mode", "default")
    file_names = common_datas.get("file_names",None)

    try:
        st = time.time()
        ret, result, f_meta = await obj.run(
                uid = uid,
                realm = realm,
                user_id = user_id,
                s3_file_path = s3_file_path.copy(),
                version_id = version_id,
                document_id = document_ids.copy(),
                published_date = published_date,
                parser_type=parser_type,
                event_id=event_id,
                parser_mode=extraction_mode,
                state = "Publish"
            )
        ed = time.time()
        if ret:
            logger.debug("Successfully completed publish upload event run.")
            logger.info(f"time-taken to run the upload publish : {ed - st} seconds.")
            
            if isinstance(f_meta, dict):
                logger.debug("The return instance is dict")
                for i, j in zip(document_ids, file_names):
                    if f_meta[j]["status"] == "Success":
                        logger.debug(f"Updating doc_id : {i}")
                        up__dat_d = await db.user_collection.update_many({"uid":uid, "realm":realm,
                                                                         f"files.{i}": {"$exists": True}},
                                                            {"$set": {f"files.{i}.status": f_meta[j]["status"]}})
                        logger.debug(f"The results for that update : {up__dat_d}")
                    
                    else:
                        logger.debug(f"Updating doc_id : {i}")
                        up__dat_f = await db.user_collection.update_many({"uid": uid, "realm": realm,
                                                                         f"files.{i}": {"$exists": True}},
                                                            {"$set": {f"files.{i}.status": "Failed"}})
                        logger.debug(f"The results for that update : {up__dat_f}")
                        
            elif isinstance(f_meta, list):
                logger.debug("the return instance is list")
                for i in document_ids:
                    logger.debug(f"Updating doc_id : {i}")
                    up_dat = await db.user_collection.update_many({"uid":uid, "realm":realm,
                                                                  f"files.{i}": {"$exists": True}},
                                                        {"$set": {f"files.{i}.status": "Success"}})
                    logger.debug(f"The results for that update : {up_dat}")
                        
            return status,error
            
                
        elif not ret and result == "AssertionError :- realm attributes does not match or no data to process.":
            logger.debug(f"Error triggered")          
            raise Exception("AssertionError :- realm attributes does not match or no data to process.")
        
        else:
            logger.debug(f"Error triggered") 
            raise Exception(str(result))
        

    except Exception as e:
        status = "fail"
        error = str(e)
        
        logger.error(f"Initiated the error in the publish consume process for uid : {uid}")
        logger.error(f"the error is : {error}")
        
        for i in document_ids:
            logger.debug(f"Updating doc_id : {i}")
            f_d = await db.user_collection.update_many({"uid": uid, "realm": realm,
                                                       f"files.{i}": {"$exists": True}},
                                                {"$set": {f"files.{i}.status": "Failed"}})
            logger.debug(f"The results for that update : {f_d}")
        
        return status,error

async def main():
    consumer = RabbitMQConsumer()
    await consumer.start_consuming()

if __name__ == "__main__":
    asyncio.run(main())