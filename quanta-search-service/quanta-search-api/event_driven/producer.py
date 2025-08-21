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
import json
import uuid
import asyncio
import aio_pika
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from utils.load_envs import env

async def connect():
    while True:
        print("Trying to connect to RabbitMQ...")
        print(env.RABBIT_HOST)
        try:
            
            connection = await aio_pika.connect(
                host=env.RABBIT_HOST,
                port=int(env.RABBIT_PORT),
                heartbeat=600,
                connection_attempts=5,
                retry_delay=0.5,
            )
            print("Connected to RabbitMQ")
            return connection
        except (aio_pika.exceptions.AMQPConnectionError) as e:
            print(f"Error connecting to RabbitMQ: {e}")
            await asyncio.sleep(3)


async def add_queue(job: dict):
    connection = await connect()
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange('topic', aio_pika.ExchangeType.TOPIC)

        try:
            await channel.declare_queue('production_docsearch_files_producer')
            await exchange.publish(
                aio_pika.Message(body =json.dumps(job).encode()),
                routing_key = job.pop("route_key")
            )
            return True

        except Exception as e:
            raise e
        

async def add_delete_queue(job_data:dict):
    connection = await connect()
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange('delete', aio_pika.ExchangeType.TOPIC)
        
        corr_id = str(uuid.uuid4())
        reply_queue_name = f"reply_queue_{corr_id}"
        reply_queue = await channel.declare_queue(
            name=reply_queue_name,
            exclusive=False, 
            durable=False, 
            auto_delete=True,
            arguments={"x-max-priority": 10, "x-message-ttl": 300000}
        )
        
        job_data["reply"] = reply_queue.name
        job_data["correlation_id"] = corr_id

        try:
            await channel.declare_queue('production_docsearch_delete_producer')
            await exchange.publish(
                aio_pika.Message(body =json.dumps(job_data).encode()),
                routing_key = job_data.pop("route_key")
            )
            return {"correlation_id":corr_id, "reply_queue_name": reply_queue.name}

        except Exception as e:
            raise e
        

async def get_msg_from_reply_queue(reply_name_name: str, correlation_id:str):
    connection = None
    try:
        print(f"\n\n\n getting mesg from queue: {reply_name_name} \n\n\n")
        connection = await connect()
        channel = await connection.channel()
        await asyncio.sleep(0.1)
        
        try:
            queue = await channel.get_queue(reply_name_name)
        except Exception:
            queue = await channel.declare_queue(
                name=reply_name_name,
                exclusive=False, 
                durable=False, 
                auto_delete=True,
                arguments={"x-max-priority": 10, "x-message-ttl": 300000}
            )
        
        active = True
        timeout_counter = 0
        max_timeout = 300
        
        async with queue.iterator() as queue_iter:
            while active and timeout_counter < max_timeout:
                try:
                    async for message in queue_iter:
                        async with message.process():
                            if message.correlation_id == correlation_id:
                                event_data = json.loads(message.body.decode())
                                yield f"data: {json.dumps(event_data)}\n"
                                
                                if event_data.get("data", {}).get("done", False):
                                    active = False
                                    break
                    
                    if active:
                        await asyncio.sleep(0.1)
                        timeout_counter += 1
                        
                except asyncio.TimeoutError:
                    timeout_counter += 1
                    if timeout_counter >= max_timeout:
                        yield f"data: {json.dumps({'error': 'Timeout waiting for response'})}\n"
                        break
                        
    except Exception as e:
        error_msg = f"Error accessing reply queue: {str(e)}"
        print(f"\n\n{error_msg}\n")
        yield f"data: {json.dumps({'error': error_msg})}\n"
    finally:
        if connection:
            await connection.close()
        

async def delete_reply_queue(queue_name:str) -> bool:
    connection = None
    try:
        print("\n\n\n deleteing queue \n\n\n")
        connection = await connect()
        channel = await connection.channel()
        queue = await channel.get_queue(queue_name, ensure=False)

        await queue.delete(if_unused=False, if_empty=False)
        print(f"Queue '{queue_name}' deleted successfully.")
        return True
    
    except Exception as e:
        print(f"Error deleting queue: {e}")
        return False
    finally:
        if connection:
            await connection.close()
