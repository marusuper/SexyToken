#!/usr/bin/env python3
"""
CLIProxyAPI Usage Statistics Report Tool

This script retrieves usage statistics from CLIProxyAPI's management API,
calculates costs based on configured token pricing, and outputs in rich table format.
"""

import json
import os
import sys
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import requests
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich.align import Align
# No longer need token_icon module, logo display functionality has been removed
# Import configuration and GLM token parser
try:
    from conf.conf import CLI_PROXY_ENABLED, GLM_ENABLED
    from src.glm_token_parser import GLMTokenParser
    from conf.log_conf import GLM_LOG_DIRECTORY
except ImportError:
    # If running script directly, try relative imports
    import sys
    import os
    # Add project root directory to Python path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from conf.conf import CLI_PROXY_ENABLED, GLM_ENABLED
    from src.glm_token_parser import GLMTokenParser
    from conf.log_conf import GLM_LOG_DIRECTORY

class UsageReporter:
    """Usage Statistics Reporter"""
    
    def __init__(self, api_url: str = "http://localhost:8317",
                 management_key: str = "",
                 pricing_config: str = "conf/token_pricing.json",
                 glm_log_directory: str = GLM_LOG_DIRECTORY):
        """
        Initialize Usage Statistics Reporter
        
        Args:
            api_url: CLIProxyAPI service URL
            management_key: Management API key
            pricing_config: Token pricing configuration file path
            glm_log_directory: GLM log file directory path
        """
        self.api_url = api_url.rstrip('/')
        self.management_key = management_key
        self.pricing_config_path = pricing_config
        self.console = Console()
        self.pricing_config = self._load_pricing_config()
        self.glm_parser = GLMTokenParser(glm_log_directory)
        
    def _load_pricing_config(self) -> Dict[str, Any]:
        """Load token pricing configuration"""
        try:
            with open(self.pricing_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.console.print(f"[red]Pricing configuration file not found: {self.pricing_config_path}[/red]")
            sys.exit(1)
        except json.JSONDecodeError as e:
            self.console.print(f"[red]Pricing configuration file format error: {e}[/red]")
            sys.exit(1)
    
    def _get_pricing_for_model(self, model_name: str) -> Tuple[float, float]:
        """
        Get token pricing for specified model
        
        Args:
            model_name: Model name
            
        Returns:
            (Input token per million price, Output token per million price)
        """
        models = self.pricing_config.get("models", {})
        default_pricing = self.pricing_config.get("pricing", {}).get("default", {})
        
        if model_name in models:
            model_config = models[model_name]
            return (
                model_config.get("input_token_per_million", default_pricing.get("input_token_per_million", 1.0)),
                model_config.get("output_token_per_million", default_pricing.get("output_token_per_million", 7.5))
            )
        else:
            return (
                default_pricing.get("input_token_per_million", 1.0),
                default_pricing.get("output_token_per_million", 7.5)
            )
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int, model_name: str) -> Tuple[float, float, float]:
        """
        Calculate token usage cost
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model_name: Model name
            
        Returns:
            (Input cost, Output cost, Total cost)
        """
        input_price_per_million, output_price_per_million = self._get_pricing_for_model(model_name)
        
        input_cost = (input_tokens / 1_000_000) * input_price_per_million
        output_cost = (output_tokens / 1_000_000) * output_price_per_million
        total_cost = input_cost + output_cost
        
        return input_cost, output_cost, total_cost
    
    def fetch_usage_data(self) -> Dict[str, Any]:
        """Fetch usage statistics from management API"""
        url = f"{self.api_url}/v0/management/usage"
        headers = {}
        
        if self.management_key:
            headers["Authorization"] = f"Bearer {self.management_key}"
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.console.print(f"[red]Failed to fetch usage data: {e}[/red]")
            sys.exit(1)
    
    def _format_currency(self, amount: float) -> str:
        """Format currency display"""
        return f"${amount:.4f}"
    
    def _format_number(self, num: int) -> str:
        """Format number display"""
        return f"{num:,}"
    
    def generate_daily_report(self, usage_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate daily statistics report
        
        Args:
            usage_data: Usage statistics data
            
        Returns:
            List of daily statistics reports
        """
        daily_report = []
        usage = usage_data.get("usage", {})
        apis = usage.get("apis", {})
        
        # Collect all dates
        all_dates = set()
        for api_endpoint, api_data in apis.items():
            for model_name, model_data in api_data.get("models", {}).items():
                for detail in model_data.get("details", []):
                    timestamp = detail.get("timestamp", "")
                    if timestamp:
                        date = timestamp.split("T")[0]
                        all_dates.add(date)
        
        # Decide whether to add dates from GLM logs based on configuration
        if GLM_ENABLED:
            glm_dates = self.glm_parser.get_available_dates()
            all_dates.update(glm_dates)
        
        # Generate statistics for each date
        for date in sorted(all_dates):
            date_stats = {
                "date": date,
                "total_requests": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "total_input_cost": 0.0,
                "total_output_cost": 0.0,
                "total_cost": 0.0,
                "models": {}
            }
            
            # Statistics for each model's usage on that date
            for api_endpoint, api_data in apis.items():
                for model_name, model_data in api_data.get("models", {}).items():
                    model_date_stats = {
                        "requests": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                        "input_cost": 0.0,
                        "output_cost": 0.0,
                        "total_cost": 0.0
                    }
                    
                    for detail in model_data.get("details", []):
                        timestamp = detail.get("timestamp", "")
                        if timestamp and timestamp.startswith(date):
                            tokens = detail.get("tokens", {})
                            input_tokens = tokens.get("input_tokens", 0)
                            output_tokens = tokens.get("output_tokens", 0)
                            total_tokens = tokens.get("total_tokens", input_tokens + output_tokens)
                            
                            input_cost, output_cost, total_cost = self._calculate_cost(
                                input_tokens, output_tokens, model_name
                            )
                            
                            # Update model statistics
                            model_date_stats["requests"] += 1
                            model_date_stats["input_tokens"] += input_tokens
                            model_date_stats["output_tokens"] += output_tokens
                            model_date_stats["total_tokens"] += total_tokens
                            model_date_stats["input_cost"] += input_cost
                            model_date_stats["output_cost"] += output_cost
                            model_date_stats["total_cost"] += total_cost
                            
                            # Update date total
                            date_stats["total_requests"] += 1
                            date_stats["total_input_tokens"] += input_tokens
                            date_stats["total_output_tokens"] += output_tokens
                            date_stats["total_tokens"] += total_tokens
                            date_stats["total_input_cost"] += input_cost
                            date_stats["total_output_cost"] += output_cost
                            date_stats["total_cost"] += total_cost
                    
                    if model_date_stats["requests"] > 0:
                        date_stats["models"][model_name] = model_date_stats
            
            # Decide whether to add GLM log data based on configuration
            if GLM_ENABLED:
                glm_data = self.glm_parser.parse_log_file(date)
                if glm_data["total_requests"] > 0:
                    # Group statistics by GLM model name
                    glm_model_groups = {}
                    for detail in glm_data.get("details", []):
                        model_name = detail.get("model", "unknown")
                        if model_name not in glm_model_groups:
                            glm_model_groups[model_name] = {
                                "requests": 0,
                                "input_tokens": 0,
                                "output_tokens": 0,
                                "total_tokens": 0,
                                "input_cost": 0.0,
                                "output_cost": 0.0,
                                "total_cost": 0.0
                            }
                        
                        tokens = detail.get("tokens", {})
                        input_tokens = tokens.get("input_tokens", 0)
                        output_tokens = tokens.get("output_tokens", 0)
                        total_tokens = tokens.get("total_tokens", input_tokens + output_tokens)
                        
                        # Update model group statistics
                        glm_model_groups[model_name]["requests"] += 1
                        glm_model_groups[model_name]["input_tokens"] += input_tokens
                        glm_model_groups[model_name]["output_tokens"] += output_tokens
                        glm_model_groups[model_name]["total_tokens"] += total_tokens
                    
                    # Calculate costs for each GLM model and add to date statistics
                    for model_name, model_stats in glm_model_groups.items():
                        # Calculate costs
                        input_cost, output_cost, total_cost = self._calculate_cost(
                            model_stats["input_tokens"],
                            model_stats["output_tokens"],
                            model_name
                        )
                        
                        model_stats["input_cost"] = input_cost
                        model_stats["output_cost"] = output_cost
                        model_stats["total_cost"] = total_cost
                        
                        # Update date total
                        date_stats["total_requests"] += model_stats["requests"]
                        date_stats["total_input_tokens"] += model_stats["input_tokens"]
                        date_stats["total_output_tokens"] += model_stats["output_tokens"]
                        date_stats["total_tokens"] += model_stats["total_tokens"]
                        date_stats["total_input_cost"] += input_cost
                        date_stats["total_output_cost"] += output_cost
                        date_stats["total_cost"] += total_cost
                        
                        # Add to model statistics
                        date_stats["models"][model_name] = model_stats
            
            if date_stats["total_requests"] > 0:
                daily_report.append(date_stats)
        
        return daily_report
    
    def display_daily_summary_table(self, daily_report: List[Dict[str, Any]]):
        """Display daily summary table"""
        if not daily_report:
            self.console.print("[yellow]No usage data found[/yellow]")
            return
        
        table = Table(title="Daily Usage Statistics Summary")
        table.add_column("Date", style="cyan", no_wrap=True)
        table.add_column("Requests", justify="right", style="magenta")
        table.add_column("Input Tokens", justify="right", style="blue")
        table.add_column("Output Tokens", justify="right", style="blue")
        table.add_column("Total Tokens", justify="right", style="blue")
        table.add_column("Input Cost", justify="right", style="green")
        table.add_column("Output Cost", justify="right", style="green")
        table.add_column("Total Cost", justify="right", style="green")
        
        total_requests = 0
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0
        total_input_cost = 0.0
        total_output_cost = 0.0
        total_cost = 0.0
        
        for day_stats in daily_report:
            table.add_row(
                day_stats["date"],
                self._format_number(day_stats["total_requests"]),
                self._format_number(day_stats["total_input_tokens"]),
                self._format_number(day_stats["total_output_tokens"]),
                self._format_number(day_stats["total_tokens"]),
                self._format_currency(day_stats["total_input_cost"]),
                self._format_currency(day_stats["total_output_cost"]),
                self._format_currency(day_stats["total_cost"])
            )
            
            total_requests += day_stats["total_requests"]
            total_input_tokens += day_stats["total_input_tokens"]
            total_output_tokens += day_stats["total_output_tokens"]
            total_tokens += day_stats["total_tokens"]
            total_input_cost += day_stats["total_input_cost"]
            total_output_cost += day_stats["total_output_cost"]
            total_cost += day_stats["total_cost"]
        
        # Add total row
        table.add_row(
            "[bold]Total[/bold]",
            f"[bold]{self._format_number(total_requests)}[/bold]",
            f"[bold]{self._format_number(total_input_tokens)}[/bold]",
            f"[bold]{self._format_number(total_output_tokens)}[/bold]",
            f"[bold]{self._format_number(total_tokens)}[/bold]",
            f"[bold]{self._format_currency(total_input_cost)}[/bold]",
            f"[bold]{self._format_currency(total_output_cost)}[/bold]",
            f"[bold]{self._format_currency(total_cost)}[/bold]"
        )
        
        self.console.print(table)
    
    def display_daily_model_details(self, daily_report: List[Dict[str, Any]]):
        """Display detailed usage for each model per day"""
        for day_stats in daily_report:
            date = day_stats["date"]
            models = day_stats["models"]
            
            if not models:
                continue
                
            table = Table(title=f"{date} - Model Usage Details")
            table.add_column("Model", style="cyan")
            table.add_column("Requests", justify="right", style="magenta")
            table.add_column("Input Tokens", justify="right", style="blue")
            table.add_column("Output Tokens", justify="right", style="blue")
            table.add_column("Total Tokens", justify="right", style="blue")
            table.add_column("Input Cost", justify="right", style="green")
            table.add_column("Output Cost", justify="right", style="green")
            table.add_column("Total Cost", justify="right", style="green")
            
            for model_name, model_stats in models.items():
                table.add_row(
                    model_name,
                    self._format_number(model_stats["requests"]),
                    self._format_number(model_stats["input_tokens"]),
                    self._format_number(model_stats["output_tokens"]),
                    self._format_number(model_stats["total_tokens"]),
                    self._format_currency(model_stats["input_cost"]),
                    self._format_currency(model_stats["output_cost"]),
                    self._format_currency(model_stats["total_cost"])
                )
            
            self.console.print(table)
            self.console.print()  # Add empty line for separation
    
    
    def run(self, show_details: bool = False, show_total_only: bool = False):
        """Run report generator"""
        try:
            usage_data = {}
            
            # Decide whether to fetch CLIProxy data based on configuration
            if CLI_PROXY_ENABLED:
                usage_data = self.fetch_usage_data()
            
            # Generate daily report
            daily_report = self.generate_daily_report(usage_data)
            
            # Display daily summary table
            self.display_daily_summary_table(daily_report)
            
            # If needed, show detailed model information (only when show_total_only is False)
            if show_details and not show_total_only:
                self.console.print()
                self.display_daily_model_details(daily_report)
                
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Operation cancelled[/yellow]")
            sys.exit(1)
        except Exception as e:
            self.console.print(f"[red]Error occurred while generating report: {e}[/red]")
            sys.exit(1)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="CLIProxyAPI Usage Statistics Report Tool")
    parser.add_argument("--url", default="http://localhost:8317",
                       help="CLIProxyAPI service URL (default: http://localhost:8317)")
    parser.add_argument("--key", default="",
                       help="Management API key")
    parser.add_argument("--config", default="conf/token_pricing.json",
                       help="Token pricing configuration file path (default: conf/token_pricing.json)")
    parser.add_argument("--glm-log-dir", default=GLM_LOG_DIRECTORY,
                       help=f"GLM log file directory path (default: {GLM_LOG_DIRECTORY})")
    parser.add_argument("--details", action="store_true",
                       help="Show detailed usage for each model per day")
    parser.add_argument("--total", action="store_true",
                       help="Show summary information only, without model details")
    
    args = parser.parse_args()
    
    # Get management key from environment variable (if not provided via command line)
    management_key = args.key or os.environ.get("CLI_PROXY_MANAGEMENT_KEY", "")
    
    if not management_key:
        console = Console()
        console.print("[yellow]Warning: No management key provided, attempting access without key[/yellow]")
    
    # Create and run reporter
    reporter = UsageReporter(
        api_url=args.url,
        management_key=management_key,
        pricing_config=args.config,
        glm_log_directory=args.glm_log_dir
    )
    
    reporter.run(show_details=args.details, show_total_only=args.total)


if __name__ == "__main__":
    main()