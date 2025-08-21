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
from urllib.parse import unquote

from utils.util import _get_job_data

from ameya_dataprocessing.core.files.schema import Job
from ameya_dataprocessing.parsers.pdf.extractors import PDFExtractor
from ameya_dataprocessing.parsers.txt.extractors import TxtExtractor
from ameya_dataprocessing.parsers.csv.extractors import CsvExtractor
from ameya_dataprocessing.parsers.doc.extractors import DocsExtractor
from ameya_dataprocessing.parsers.excel.extractors import ExcelExtractor


class FileExtractors:
    
    def __init__(self):
        self.txt_extract = TxtExtractor()
        self.csv_extract = CsvExtractor()
        self.pdf_extract = PDFExtractor()
        self.doc_extract = DocsExtractor()
        self.excel_extract = ExcelExtractor()
    
    async def aload_data(self, file_path:str, file_name:str, checksum:str):
        
        _, ext = os.path.splitext(unquote(os.path.split(file_path.split("?")[0])[-1]))
        assert ext in [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".txt"], "Unsupported extension is given."
        
        if ext == ".pdf":
            job_data = Job.model_validate(_get_job_data())
            
            job_data.file_path = [file_path]
            job_data.plan = "basic +"
            job_data.correlation_id = job_data.job_id
            job_data.checksums = {file_name: checksum}
            
            docs = await self.pdf_extract.extract(job_data)
        
        elif ext == ".csv":
            job_data = Job.model_validate(_get_job_data())
            
            job_data.file_path = [file_path]
            job_data.plan = "basic"
            job_data.correlation_id = job_data.job_id
            job_data.checksums = {file_name: checksum}
            
            docs = await self.csv_extract.extract(job_data)
        
        elif ext == ".txt":
            job_data = Job.model_validate(_get_job_data())
            
            job_data.file_path = [file_path]
            job_data.plan = "basic"
            job_data.correlation_id = job_data.job_id
            job_data.checksums = {file_name: checksum}
            
            docs = await self.txt_extract.extract(job_data)
        
        elif ext in [".docx", ".doc"]:
            job_data = Job.model_validate(_get_job_data())
            
            job_data.file_path = [file_path]
            job_data.plan = "basic +"
            job_data.correlation_id = job_data.job_id
            job_data.checksums = {file_name: checksum}
            
            docs = await self.doc_extract.extract(job_data)
        
        elif ext in [".xlsx", ".xls"]:
            job_data = Job.model_validate(_get_job_data())
            
            job_data.file_path = [file_path]
            job_data.plan = "basic"
            job_data.correlation_id = job_data.job_id
            job_data.checksums = {file_name: checksum}
            
            docs = await self.excel_extract.extract(job_data)
        
        return docs