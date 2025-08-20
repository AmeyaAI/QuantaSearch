import os
import json
from typing import Dict,Optional, Any
from fastapi import HTTPException
from requests.utils import unquote
from pydantic import BaseModel, field_validator, model_validator, PrivateAttr

from llama_index.core.workflow import Event
from llama_index.core.schema import TextNode, NodeWithScore, Document

from utils.load_envs import env
from logger.api_logger import logger

supported_formats = [".pdf",".docx", ".doc", ".txt", ".csv", ".xls", ".xlsx"]

if env.REALM_CONFIG_JSON_PATH:
    with open(env.REALM_CONFIG_JSON_PATH, "rb") as f:
        r_keys = json.load(f)["realm_keys"]

elif env.REALM_KEYS:
    r_keys = [i.strip() for i in env.REALM_KEYS.strip().split(",")]
    
else:
    r_keys = []
            
        
###################################################################################################


class FileParseEvent(Event):
    dir_path : str
    file_meta : dict
    realm : dict
    uid : str
    user_id : str
    state : str
    version_id : str | int
    parser_type : str = "docling"
    parser_mode : str = "default"
    published_date : str | int | None = None
    version_change_date: str | int | None = None
    uploaded_date: str | int | None = None

class MetaUpdateEvent(Event):
    docs : list[Document | TextNode]
    uid : str
    user_id : str
    state : str
    realm : dict
    version_id : str | int
    file_meta : dict
    published_date : str | int | None = None
    version_change_date: str | int | None = None
    uploaded_date: str | int | None = None
    
class UserCollectionUpdate(Event):
    docs : list[Document | TextNode]
    uid : str
    state : str
    realm : dict
    version_id : str | int
    file_meta : dict

class VectorUploadEvent(Event):
    docs : list[Document | TextNode]
    uid: str
    
class IndexUpdateEvent(Event):
    docs : list[dict]
    uid : str 
    ids : list | Any

class RerankEvent(Event):
    nodes : list[NodeWithScore]
    query : str
    result : list[tuple]
    
    
    
########################################################################################################


class DraftUpload(BaseModel):
    document_download_url : str | list
    user_id : str
    realm : dict
    document_id : str | list
    uploaded_date : str | int
    _extarction_mode: str = "default"
    _parser_type : str = PrivateAttr("docling")
    
    @field_validator("document_download_url")
    def validate_file_extension(cls, url):
        for i in [url] if isinstance(url, str) else url:
            extension = os.path.splitext(unquote(os.path.split(i.split("?")[0])[-1]))[-1].lower()
            if extension not in supported_formats:
                logger.error("unsupport file type")
                raise HTTPException(status_code=415,detail="Unsupported File Type")
        return url
    
    
    @model_validator(mode="after")
    def validate_realm_keys(self):

        try:
            logger.info("Entered draft upload data......")
            assert type(self.document_download_url) == type(self.document_id), "document_id and documnet_download url must be of same type."
            
            if isinstance(self.document_download_url, list):
                assert len(self.document_download_url) == len(self.document_id), "document_id and documnet_download url must be of same size."
            
        except Exception as e:
            logger.error("got document mismatch error......")
            raise HTTPException(status_code=400, detail=f"document mismatch error {str(e)}")
         
        if r_keys and not self.realm:
            logger.error("got realm not be empty error......")
            raise HTTPException(status_code=405, detail="Realm attribute found, So realm must not be empty.")
            
        elif r_keys and set(list(self.realm.keys())).symmetric_difference(r_keys):
            logger.error("got unspport realm error......")
            raise HTTPException(status_code=406, detail="unsupported realm keys are given")
        
        elif not r_keys and self.realm:
            logger.error("got realm must empty error......")
            raise HTTPException(status_code=405, detail="Realm attribute not found. So realm must be empty.")
            
        return self
        
        
            
    

class PublishUpload(BaseModel):
    document_download_url : str | list
    user_id : str
    realm : dict
    document_id : str | list
    version_id : str
    published_date : str | int
    _extarction_mode: str = "default"
    _parser_type : str = PrivateAttr("docling")
    
    @field_validator("document_download_url")
    def validate_file_extension(cls, url):
        for i in [url] if isinstance(url, str) else url:
            extension = os.path.splitext(unquote(os.path.split(i.split("?")[0])[-1]))[-1].lower()
            if extension not in supported_formats:
                raise HTTPException(status_code=415,detail="Unsupported File Type")
        return url
    
    
    @model_validator(mode="after")
    def validate_realm_keys(self):
        
        try:
            logger.info("Entered publish upload data......")
            assert type(self.document_download_url) == type(self.document_id), "document_id and documnet_download url must be of same type."
            
            if isinstance(self.document_download_url, list):
                assert len(self.document_download_url) == len(self.document_id), "document_id and documnet_download url must be of same size."
            
            assert self.version_id, "version_id must not be empty."
            
        except Exception as e:
            logger.error("got document mismatch error......")
            raise HTTPException(status_code=400, detail=f"document mismatch error {str(e)}")
   
        if r_keys and not self.realm:
            logger.error("got realm not be empty error......")
            raise HTTPException(status_code=405, detail="Realm attribute found, So realm must not be empty.")
            
        elif r_keys and set(list(self.realm.keys())).symmetric_difference(r_keys):
            logger.error("got unspport realm error......")
            raise HTTPException(status_code=406, detail="unsupported realm keys are given")
        
        elif not r_keys and self.realm:
            logger.error("got realm must empty error......")
            raise HTTPException(status_code=405, detail="Realm attribute not found. So realm must be empty.")
            
        return self
        
        
class VersionChange(BaseModel):
    realm : dict
    document_id : str
    user_id : str 
    marked_latest_version : str | int
    version_change_date : str | int


class DeleteFile(BaseModel):
    realm : dict
    document_id : str
    user_id : str
    version_id : str | int | None = None
    state : str


class Filelister(BaseModel):
    user_id : str
    realm : Optional[dict] = None
    
    @model_validator(mode="after")
    def validate_realm_keys(self):

        if self.realm and set(list(self.realm.keys())).difference(r_keys):
            raise HTTPException(status_code=406, detail="unsupported realm keys are given")
        
        return self


class QueryRequest(BaseModel):
    query: str
    realm : dict
    user_id : str
    state : str = "Publish"
    exact_match : bool = False
    
    @model_validator(mode="after")
    def validate_realm_keys(self):
        
        assert env.PREVIEW_LENGTH > 0, "The preview length must be greater than 0."
        
        if self.realm and set(list(self.realm.keys())).difference(r_keys):
            raise HTTPException(status_code=406, detail="unsupported realm keys are given")

        return self


class PreviewBody(BaseModel):
    query:str
    user_id:str
    document_id:str
    state:str
    realm:dict = {}
    
    
    @model_validator(mode="after")
    def validate_preview_body(self):

        try:
            assert env.PREVIEW_LENGTH > 0, "The preview length must be greater than 0."
        
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"preview length error {str(e)}")

        return self
    