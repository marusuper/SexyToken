#!/usr/bin/env python3
"""
GLM Token Usage Log Parser

This module is used to parse GLM model token usage log files,
extract input and output token quantities, and perform statistics by date.
"""

import json
import os
import re
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from rich.console import Console

# Add project root directory to Python path to import configuration module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import GLM log directory configuration
from conf.log_conf import GLM_LOG_DIRECTORY


class GLMTokenParser:
    """GLM Token Usage Log Parser"""
    
    def __init__(self, log_directory: str = GLM_LOG_DIRECTORY):
        """
        Initialize GLM Token Parser
        
        Args:
            log_directory: Log file directory path
        """
        self.log_directory = log_directory
        self.console = Console()
    
    def parse_log_file(self, date: str) -> Dict[str, Any]:
        """
        Parse log file for specified date
        
        Args:
            date: Date string in YYYY-MM-DD format
            
        Returns:
            Token usage statistics for that date
        """
        log_file_path = os.path.join(self.log_directory, f"token_usage_{date}.log")
        
        if not os.path.exists(log_file_path):
            self.console.print(f"[yellow]Log file does not exist: {log_file_path}[/yellow]")
            return {
                "date": date,
                "total_requests": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "details": []
            }
        
        date_stats = {
            "date": date,
            "total_requests": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "details": []
        }
        
        try:
            with open(log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Parse complete JSON line
                    try:
                        log_entry = json.loads(line)
                        
                        # Extract timestamp
                        timestamp = log_entry.get("timestamp", "")
                        
                        # Extract model name
                        model_name = log_entry.get("model", "unknown")
                        
                        # Extract token usage data
                        token_usage = log_entry.get("token_usage", {})
                        prompt_tokens = token_usage.get("prompt_tokens", 0)
                        completion_tokens = token_usage.get("completion_tokens", 0)
                        total_tokens = token_usage.get("total_tokens", prompt_tokens + completion_tokens)
                        
                        # Update statistics
                        date_stats["total_requests"] += 1
                        date_stats["total_input_tokens"] += prompt_tokens
                        date_stats["total_output_tokens"] += completion_tokens
                        date_stats["total_tokens"] += total_tokens
                        
                        # Add detailed information
                        date_stats["details"].append({
                            "timestamp": timestamp,
                            "model": model_name,
                            "tokens": {
                                "input_tokens": prompt_tokens,
                                "output_tokens": completion_tokens,
                                "total_tokens": total_tokens
                            }
                        })
                    
                    except (json.JSONDecodeError, ValueError) as e:
                        self.console.print(f"[yellow]Error parsing log line: {e}[/yellow]")
                        continue
        
        except FileNotFoundError:
            self.console.print(f"[red]Log file not found: {log_file_path}[/red]")
        except Exception as e:
            self.console.print(f"[red]Error reading log file: {e}[/red]")
        
        return date_stats
    
    def get_available_dates(self) -> List[str]:
        """
        Get all available log file dates
        
        Returns:
            List of dates in YYYY-MM-DD format
        """
        if not os.path.exists(self.log_directory):
            return []
        
        dates = []
        try:
            for filename in os.listdir(self.log_directory):
                if filename.startswith("token_usage_") and filename.endswith(".log"):
                    # Extract date part
                    date_part = filename[12:-4]  # Remove "token_usage_" prefix and ".log" suffix
                    if re.match(r"\d{4}-\d{2}-\d{2}", date_part):
                        dates.append(date_part)
        except Exception as e:
            self.console.print(f"[red]Error reading log directory: {e}[/red]")
        
        return sorted(dates)
    
    def merge_with_api_data(self, glm_data: Dict[str, Any], api_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge GLM log data with API data
        
        Args:
            glm_data: GLM log data
            api_data: API data
            
        Returns:
            Merged data
        """
        # Get usage statistics from API data
        usage = api_data.get("usage", {})
        apis = usage.get("apis", {})
        
        # Find GLM related API data
        glm_api_data = None
        for api_endpoint, api_info in apis.items():
            if "glm" in api_endpoint.lower():
                glm_api_data = api_info
                break
        
        if not glm_api_data:
            # If no GLM related API data found, create a new one
            glm_api_data = {
                "models": {
                    "glm": {
                        "details": []
                    }
                }
            }
        
        # Add GLM log data to API data
        glm_models = glm_api_data.get("models", {})
        if "glm" not in glm_models:
            glm_models["glm"] = {"details": []}
        
        # Merge detailed information
        glm_models["glm"]["details"].extend(glm_data.get("details", []))
        
        # Update API data
        if not apis.get("glm"):
            apis["glm"] = glm_api_data
        
        return api_data