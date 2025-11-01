#!/usr/bin/env python3
"""
Log Configuration File Example

This file is an example template for log configuration. Please copy it as log_conf.py and modify the configuration according to your actual situation.
"""

# GLM Token log file directory path
# Please modify according to your actual log storage path
GLM_LOG_DIRECTORY = "D:\\logs"

# Log file name format
# {date} will be replaced with the actual date, format is YYYY-MM-DD
LOG_FILE_FORMAT = "token_usage_{date}.log"

# Date format
# Used for the date part in log file names
DATE_FORMAT = "%Y-%m-%d"

# Other possible configuration examples:
# LOG_LEVEL = "INFO"  # Log level
# MAX_LOG_SIZE = 100 * 1024 * 1024  # Maximum log file size (bytes)
# LOG_ROTATION = "daily"  # Log rotation strategy