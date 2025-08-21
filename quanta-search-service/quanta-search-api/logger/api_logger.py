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
import logging
from utils.load_envs import env


class Logging:
    _instance = None
    def __new__(cls):

        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls.logger = logging.getLogger(__name__)
            cls.logger.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')
            os.makedirs("temp/logs", mode=0o777, exist_ok=True)
            file_handler = logging.FileHandler('temp/logs/file_search_manager_api_app.log')
            file_handler.setFormatter(formatter)
            cls.logger.addHandler(file_handler)
        return cls._instance
    
    def info(self,message):
        self.logger.info(message)

    def warning(self,message):
        self.logger.warning(message)

    def error(self,message):
        self.logger.error(message)

    def exception(self,message):
        self.logger.exception(message)
    
    def debug(self,message):
        self.logger.debug(message)


logger = Logging()