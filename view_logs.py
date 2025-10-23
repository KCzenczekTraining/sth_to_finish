#!/usr/bin/env python3
"""Log viewer and analyzer for audio server logs."""

import argparse
import logging
import re
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Union

# ANSI color codes
class Colors:
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    RESET = '\033[0m'

# Constants
DEFAULT_LINES = 50
FOLLOW_SLEEP = 0.1
MB_DIVISOR = 1024 * 1024


def tail_file(filepath: Path, lines: int = DEFAULT_LINES) -> List[str]:
    """Get last N lines from file efficiently."""
    try:
        with filepath.open('r', encoding='utf-8') as f:
            # Use deque for efficient tail operation
            from collections import deque
            return list(deque(f, maxlen=lines))
    except FileNotFoundError:
        return [f"Log file not found: {filepath}\n"]
    except (OSError, UnicodeDecodeError) as e:
        return [f"Error reading log file {filepath}: {e}\n"]


def colorize_line(line: str) -> str:
    """Apply color formatting to log line based on level."""
    line = line.rstrip()
    if "ERROR" in line:
        return f"{Colors.RED}{line}{Colors.RESET}"
    elif "WARNING" in line:
        return f"{Colors.YELLOW}{line}{Colors.RESET}"
    elif "INFO" in line:
        return f"{Colors.GREEN}{line}{Colors.RESET}"
    return line

def follow_log(filepath: Path) -> None:
    """Follow a log file in real-time (like tail -f)."""
    try:
        with filepath.open('r', encoding='utf-8') as f:
            f.seek(0, 2)  # Go to end of file
            
            while True:
                line = f.readline()
                if not line:
                    time.sleep(FOLLOW_SLEEP)
                    continue
                print(colorize_line(line))
                    
    except KeyboardInterrupt:
        print("\nLog following stopped.")
    except FileNotFoundError:
        print(f"Log file not found: {filepath}")
    except (OSError, UnicodeDecodeError) as e:
        print(f"Error following log file: {e}")


def analyze_logs(log_dir: Path) -> None:
    """Analyze logs and provide comprehensive statistics."""
    stats = {
        'total_requests': 0,
        'uploads': 0,
        'downloads': 0,
        'lists': 0,
        'health_checks': 0,
        'errors': 0,
        'warnings': 0,
        'users': set(),
        'file_sizes': [],
        'response_times': []
    }
    
    # Patterns for v1 API endpoints
    upload_pattern = re.compile(r'POST.*?/api/v1/audio/upload')
    download_pattern = re.compile(r'GET.*?/api/v1/audio/download')
    list_pattern = re.compile(r'GET.*?/api/v1/audio/list')
    health_pattern = re.compile(r'GET.*?/api/v1/health')
    user_pattern = re.compile(r'user_id=([^\s|]+)')
    
    # Analyze main log file
    main_log = log_dir / "audio_server.log"
    if main_log.exists():
        with main_log.open('r', encoding='utf-8') as f:
            for line in f:
                if "ERROR" in line:
                    stats['errors'] += 1
                elif "WARNING" in line:
                    stats['warnings'] += 1
                elif "method=" in line:  # Access log format
                    stats['total_requests'] += 1
                    if upload_pattern.search(line):
                        stats['uploads'] += 1
                    elif download_pattern.search(line):
                        stats['downloads'] += 1
                    elif list_pattern.search(line):
                        stats['lists'] += 1
                    elif health_pattern.search(line):
                        stats['health_checks'] += 1
                
                # Extract user IDs using regex
                user_match = user_pattern.search(line)
                if user_match:
                    user_id = user_match.group(1)
                    if user_id and user_id != "anonymous":
                        stats['users'].add(user_id)
    
    # Analyze access log file
    access_log = Path(log_dir) / "audio_server_access.log"
    if access_log.exists():
        with open(access_log, 'r', encoding='utf-8') as f:
            for line in f:
                if "response_time=" in line:
                    try:
                        time_part = [p for p in line.split(" | ") if "response_time=" in p][0]
                        response_time = float(time_part.split("=")[1].replace("s", ""))
                        stats['response_times'].append(response_time)
                    except (IndexError, ValueError):
                        pass
                
                if "file_size=" in line:
                    try:
                        size_part = [p for p in line.split(" | ") if "file_size=" in p][0]
                        file_size = int(size_part.split("=")[1].replace("bytes", ""))
                        stats['file_sizes'].append(file_size)
                    except (IndexError, ValueError):
                        pass
    
    # Display statistics
    print("=" * 60)
    print("AUDIO SERVER LOG ANALYSIS")
    print("=" * 60)
    
    # Request breakdown
    other_requests = (stats['total_requests'] - stats['uploads'] - 
                     stats['downloads'] - stats['lists'] - stats['health_checks'])
    print(f"Total Requests:     {stats['total_requests']}")
    print(f"  - Uploads:        {stats['uploads']}")
    print(f"  - Downloads:      {stats['downloads']}")
    print(f"  - Lists:          {stats['lists']}")
    print(f"  - Health Checks:  {stats['health_checks']}")
    print(f"  - Other:          {other_requests}")
    print()
    
    # Error statistics
    print(f"Errors:             {stats['errors']}")
    print(f"Warnings:           {stats['warnings']}")
    print()
    
    # User statistics
    print(f"Unique Users:       {len(stats['users'])}")
    if stats['users']:
        user_list = ', '.join(sorted(stats['users'])[:10])  # Limit display
        if len(stats['users']) > 10:
            user_list += f" (and {len(stats['users']) - 10} more)"
        print(f"User IDs:           {user_list}")
    print()
    
    # File statistics
    if stats['file_sizes']:
        avg_size = statistics.mean(stats['file_sizes'])
        total_size = sum(stats['file_sizes'])
        median_size = statistics.median(stats['file_sizes'])
        print(f"Files Processed:    {len(stats['file_sizes'])}")
        print(f"Average File Size:  {avg_size / MB_DIVISOR:.2f} MB")
        print(f"Median File Size:   {median_size / MB_DIVISOR:.2f} MB")
        print(f"Total Data:         {total_size / MB_DIVISOR:.2f} MB")
        print(f"Largest File:       {max(stats['file_sizes']) / MB_DIVISOR:.2f} MB")
        print()
    
    # Response time statistics
    if stats['response_times']:
        avg_time = statistics.mean(stats['response_times'])
        median_time = statistics.median(stats['response_times'])
        print(f"Average Response:   {avg_time:.3f} seconds")
        print(f"Median Response:    {median_time:.3f} seconds")
        print(f"Fastest Response:   {min(stats['response_times']):.3f} seconds")
        print(f"Slowest Response:   {max(stats['response_times']):.3f} seconds")
    
    print("=" * 60)


def main() -> None:
    """Main entry point for log viewer."""
    parser = argparse.ArgumentParser(description="Audio Server Log Viewer and Analyzer")
    parser.add_argument("--log-dir", type=Path, default=Path("logs"),
                       help="Directory containing log files")
    parser.add_argument("--lines", "-n", type=int, default=DEFAULT_LINES,
                       help="Number of lines to show")
    parser.add_argument("--follow", "-f", action="store_true",
                       help="Follow log in real-time")
    parser.add_argument("--analyze", "-a", action="store_true",
                       help="Analyze logs and show statistics")
    parser.add_argument("--file", choices=["main", "error", "access"], default="main",
                       help="Which log file to view")
    
    args = parser.parse_args()
    
    if not args.log_dir.exists():
        print(f"Log directory not found: {args.log_dir}")
        print("Make sure the server has been started at least once.")
        sys.exit(1)
    
    file_map = {
        "main": "audio_server.log",
        "error": "audio_server_errors.log",
        "access": "audio_server_access.log"
    }
    
    if args.analyze:
        analyze_logs(args.log_dir)
        return
    
    log_file = args.log_dir / file_map[args.file]
    
    if args.follow:
        print(f"Following {log_file} (Press Ctrl+C to stop)")
        print("-" * 60)
        follow_log(log_file)
    else:
        print(f"Last {args.lines} lines from {log_file}:")
        print("-" * 60)
        lines = tail_file(log_file, args.lines)
        for line in lines:
            print(colorize_line(line))


if __name__ == "__main__":
    main()
