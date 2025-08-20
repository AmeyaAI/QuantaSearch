import os
import logging

class Logging:
    _instance = None
    def __new__(cls):

        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls.logger = logging.getLogger(__name__)
            cls.logger.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')
            os.makedirs("temp/logs", mode=0o777, exist_ok=True)
            file_handler = logging.FileHandler('temp/logs/file_search_manager_app.log')
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