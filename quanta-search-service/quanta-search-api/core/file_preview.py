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


from typing import List
from bisect import bisect_left, bisect_right
from concurrent.futures import ProcessPoolExecutor, as_completed

from db.db import db
from utils.load_envs import env
from logger.logger import logger

def find_occurrences(text: str, query: str, limit:int) -> List[int]:
    positions = []
    i = text.find(query)
    while i != -1 and (limit < 0 or len(positions) < limit):
        positions.append(i)
        i = text.find(query, i + 1)

    return positions

def process_single_text(text: str, query: str, preview_length: int, limit:int):
    whitespace_positions = [i for i, c in enumerate(text) if c.isspace()]
    results = []
    query_len = len(query)

    for start_pos in find_occurrences(text, query, limit):
        end_pos = start_pos + query_len

        before_index = bisect_right(whitespace_positions, start_pos)
        if before_index >= preview_length:
            fourth_whitespace_before = whitespace_positions[before_index - preview_length]
        else:
            fourth_whitespace_before = 0

        after_index = bisect_left(whitespace_positions, end_pos)
        if len(whitespace_positions) - after_index >= preview_length:
            fourth_whitespace_after = whitespace_positions[after_index + preview_length - 1]
        else:
            fourth_whitespace_after = len(text)

        preview = text[fourth_whitespace_before:fourth_whitespace_after].strip()

        if "file name :" not in preview:
            results.append(preview)

    return results

def batch_texts(texts: List[str], batch_size: int):
    for i in range(0, len(texts), batch_size):
        yield texts[i:i+batch_size]

def process_batch(batch: List[str], query: str, preview_length: int, limit:int):
    batch_results = []
    for text in batch:
        batch_results.extend(process_single_text(text, query, preview_length, limit))
    return batch_results

def process_texts_in_batches(texts: List[str], query: str, preview_length: int, limit:int, batch_size: int = 50, max_workers: int = None):
    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for batch in batch_texts(texts, batch_size):
            futures.append(executor.submit(process_batch, batch, query, preview_length, limit))
        for future in as_completed(futures):
            results.extend(future.result())
    return results


async def get_preview_docs(uid:str, realm:dict, doc_id:str, state:str):
    
    flt = {"metadata.uid": uid,
           "metadata.state": state,
           "metadata.document_id": doc_id}
    flt.update({f"metadata.realm.{k}": v for k,v in realm.items()})
    
    out_docs = await db.vector_store.find(flt, {"text":1, "file_name": "$metadata.file_name", "page_no": "$metadata.page_no"},
                                          batch_size=5000).to_list()
    
    return [(i["text"].replace(f"file name : {i['file_name'].lower()}", ""),
             i.get("page_no", None)) for i in out_docs]


def process_texts(texts: List[str | tuple], query: str, preview_length: int, limit:int, max_workers: int = 4,
                  detailed_output:bool = False):
    
    results = []
    for text in texts:
        if detailed_output:
            assert isinstance(text, tuple) and len(text) == 2, "If detailed output set to True, texts must be of class<tuple> and of length 2 containing the text and page_no."
            
            previews = process_single_text(text[0], query, preview_length, limit)
            if previews:
                results.append({"page_no": text[1],
                                "previews": previews})
            continue
        
        elif isinstance(text, str):
            results.extend(process_single_text(text, query, preview_length, limit))
            
    return results