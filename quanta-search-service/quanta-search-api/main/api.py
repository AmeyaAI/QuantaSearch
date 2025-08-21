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


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from router.api import m_router

origins = [
    "*",
]

app = FastAPI(
    title="Doc Search API",
    description="API for uploading and searching similar files",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sub_app = FastAPI()

sub_app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sub_app.include_router(m_router)

@sub_app.get("/health", tags=["SYSTEM"])
async def check_api_status():
    return {"status": "healthy"}


app.mount("/quantasearch/v1", sub_app)