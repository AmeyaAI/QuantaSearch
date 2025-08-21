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
import hashlib
import requests
from requests.utils import unquote



async def download_from_presigned(presigned_url:list[str], uid:str, document_ids:list[str], event_id:str):

    file_meta = {}
    cwd = os.getcwd()
    uploaded_files = []
    os.makedirs(os.path.join(cwd, "temp_download", uid, event_id), exist_ok=True, mode=0o777)

    for idx, i in enumerate(presigned_url):
        try:
            file_name = unquote(os.path.split(i.split("?")[0])[-1])

            hasher = hashlib.new("sha256")
            data = requests.get(i, stream=True)

            with open(os.path.join(cwd, "temp_download", uid, event_id, file_name), "wb+") as f:
                for chunk in data.iter_content(131072):
                    f.write(chunk)
                    hasher.update(chunk)
            
            check = os.path.exists(os.path.join(cwd, "temp_download", uid, event_id, file_name))
            f_size = os.stat(os.path.join(cwd, "temp_download", uid, event_id, file_name)).st_size

            assert check and f_size > 0, "The downloaded file is corrupted while downloading."

            uploaded_files.append({"file_path": os.path.join(cwd, "temp_download", uid, event_id, file_name), 
                                   "dir_path": os.path.join(cwd, "temp_download", uid, event_id),
                                   "checksum": hasher.hexdigest(), "file_name": file_name,
                                   "status":"success", "error":None})
            
            file_meta[file_name] = {"document_id": document_ids[idx]}
        
        except Exception as e:
            uploaded_files.append({"file_path": os.path.join(cwd, "temp_download", uid, event_id, file_name), 
                                   "dir_path": os.path.join(cwd, "temp_download", uid, event_id),
                                   "checksum": "", "file_name": file_name,
                                   "status":"fail", "error":f"{e.__class__.__name__} : {str(e)}"})
            
    return uploaded_files, file_meta