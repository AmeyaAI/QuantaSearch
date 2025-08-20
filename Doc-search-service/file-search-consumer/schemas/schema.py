from typing import Any

from llama_index.core.workflow import Event
from llama_index.core.schema import TextNode, NodeWithScore, Document

supported_formats = [".pdf",".docx", ".doc", ".txt", ".csv", ".xls", ".xlsx"]


###################################################################################################


class FileParseEvent(Event):
    dir_path : str
    file_urls : list[dict]
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
    
class UserCollectionUpdateEvent(Event):
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
    
class ProgressEvent(Event):
    msg:str