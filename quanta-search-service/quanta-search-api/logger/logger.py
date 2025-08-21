import os
import logging

class Logging:
    _instance = None
    def __new__(cls):
        """
        Singleton pattern implementation for general application logging.
        
        Creates a single logging instance with file handler pointing to
        'temp/logs/file_search_manager_app.log' with DEBUG level
        and formatted output.
        
        Returns:
            Logging: Singleton instance of the logger
        """

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
        """
        Log an info level message.
        
        Args:
            message (str): Message to log at info level
        """
        self.logger.info(message)

    def warning(self,message):
        """
        Log a warning level message.
        
        Args:
            message (str): Message to log at warning level
        """
        self.logger.warning(message)

    def error(self,message):
        """
        Log an error level message.
        
        Args:
            message (str): Message to log at error level
        """
        self.logger.error(message)

    def exception(self,message):
        """
        Log an exception with full traceback information.
        
        Args:
            message (str): Message to log with exception details
        """
        self.logger.exception(message)
    
    def debug(self,message):
        """
        Log a debug level message.
        
        Args:
            message (str): Message to log at debug level
        """
        self.logger.debug(message)

logger = Logging()