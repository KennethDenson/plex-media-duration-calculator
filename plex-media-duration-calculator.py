#!/usr/bin/env python3
import requests
import time
import configparser
import os
import sys
from datetime import timedelta
from collections import defaultdict
import shutil
try:
    from tabulate import tabulate
    TABULATE_AVAILABLE = True
except ImportError:
    TABULATE_AVAILABLE = False

class PlexMediaCalculator:
    def __init__(self, server_url=None, token=None, config_file="plex_config.ini"):
        self.config_file = config_file
        self.server_url = server_url
        self.token = token
        self.total_duration = 0  # duration in milliseconds
        self.group_by = "type"  # default grouping
        self.media_counts = defaultdict(int)
        self.library_stats = defaultdict(lambda: {"count": 0, "duration": 0, "type": None})
        # Load configuration if not provided
        if not server_url or not token:
            self.load_config()
        self.load_group_by()
        
    def load_config(self):
        """Load Plex server URL and token from config file"""
        if os.path.exists(self.config_file):
            config = configparser.ConfigParser()
            config.read(self.config_file)
            
            if "PLEX" in config:
                self.server_url = config["PLEX"].get("server_url", self.server_url)
                self.token = config["PLEX"].get("token", self.token)
            
        if not self.server_url or not self.token:
            self.setup_config()
    
    def setup_config(self):
        """Set up the configuration file with user input"""
        print("Plex Media Calculator - First-time Setup")
        print("-----------------------------------------")
        print("This script needs your Plex server details to function.")
        
        server_url = input("Enter your Plex server URL (e.g., http://localhost:32400): ")
        token = input("Enter your Plex authentication token: ")
        
        if not server_url or not token:
            print("Error: Server URL and token are required.")
            sys.exit(1)
            
        # Save to config file
        config = configparser.ConfigParser()
        config["PLEX"] = {
            "server_url": server_url,
            "token": token
        }
        
        with open(self.config_file, "w") as f:
            config.write(f)
            
        print(f"Configuration saved to {self.config_file}")
        self.server_url = server_url
        self.token = token
    
    def load_group_by(self):
        """Load or prompt for group_by option and store in config"""
        config = configparser.ConfigParser()
        config.read(self.config_file)
        last_group_by = None
        if "OUTPUT" in config and "group_by" in config["OUTPUT"]:
            last_group_by = config["OUTPUT"]["group_by"].strip().lower()
        prompt = "How would you like to group your media summary? (type/name)"
        if last_group_by:
            prompt += f" [default: {last_group_by}]"
        prompt += ": "
        user_input = input(prompt).strip().lower()
        if user_input not in ("type", "name", ""):
            print("Invalid input. Defaulting to last used or 'type'.")
            user_input = last_group_by or "type"
        if user_input == "":
            user_input = last_group_by or "type"
        self.group_by = user_input
        # Save to config
        if "OUTPUT" not in config:
            config["OUTPUT"] = {}
        config["OUTPUT"]["group_by"] = self.group_by
        with open(self.config_file, "w") as f:
            config.write(f)
    
    def make_request(self, endpoint):
        """Make a request to the Plex API"""
        url = f"{self.server_url}{endpoint}"
        headers = {
            "X-Plex-Token": self.token,
            "Accept": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error accessing Plex API: {e}")
            return None
    
    def get_sections(self):
        """Get all library sections from Plex"""
        data = self.make_request("/library/sections")
        if not data:
            return []
            
        return data.get("MediaContainer", {}).get("Directory", [])
    
    def process_section(self, section):
        """Process a single library section"""
        section_id = section.get("key")
        section_title = section.get("title")
        section_type = section.get("type")
        
        print(f"Processing library: {section_title} ({section_type})...")
        
        # Get all items in this section
        data = self.make_request(f"/library/sections/{section_id}/all")
        if not data:
            return
            
        items = data.get("MediaContainer", {}).get("Metadata", [])
        if not items:
            print(f"  No items found in {section_title}")
            return
            
        section_duration = 0
        section_count = 0
        
        for item in items:
            if section_type == "movie":
                duration = item.get("duration", 0)
                section_duration += duration
                section_count += 1
                self.media_counts["movies"] += 1
                self.library_stats[section_title]["count"] += 1
                self.library_stats[section_title]["duration"] += duration
                self.library_stats[section_title]["type"] = section_type
                
            elif section_type == "show":
                # For shows, we need to get all episodes
                show_key = item.get("key")
                self.process_show(show_key, section_title, section_type)
                
            elif section_type == "artist":
                # For music, we need to get all albums and tracks
                artist_key = item.get("key")
                self.process_artist(artist_key, section_title, section_type)
                
            else:
                # Handle other media types
                duration = item.get("duration", 0)
                if duration:
                    section_duration += duration
                    section_count += 1
                    self.media_counts["other"] += 1
                    self.library_stats[section_title]["count"] += 1
                    self.library_stats[section_title]["duration"] += duration
                    self.library_stats[section_title]["type"] = section_type
        
        if section_type == "movie":
            self.total_duration += section_duration
            print(f"  Found {section_count} movies with total duration: {self.format_duration(section_duration)}")
    
    def process_show(self, show_key, section_title, section_type):
        """Process a TV show and all its episodes"""
        data = self.make_request(show_key)
        if not data:
            return
            
        # Get all seasons
        seasons = data.get("MediaContainer", {}).get("Metadata", [])
        for season in seasons:
            season_key = season.get("key")
            self.process_season(season_key, section_title, section_type)
    
    def process_season(self, season_key, section_title, section_type):
        """Process a TV season and all its episodes"""
        data = self.make_request(season_key)
        if not data:
            return
            
        # Get all episodes in this season
        episodes = data.get("MediaContainer", {}).get("Metadata", [])
        for episode in episodes:
            duration = episode.get("duration", 0)
            if duration:
                self.total_duration += duration
                self.media_counts["episodes"] += 1
                self.library_stats[section_title]["count"] += 1
                self.library_stats[section_title]["duration"] += duration
                self.library_stats[section_title]["type"] = section_type
    
    def process_artist(self, artist_key, section_title, section_type):
        """Process a music artist and all their tracks"""
        data = self.make_request(artist_key)
        if not data:
            return
            
        # Get all albums
        albums = data.get("MediaContainer", {}).get("Metadata", [])
        for album in albums:
            album_key = album.get("key")
            self.process_album(album_key, section_title, section_type)
    
    def process_album(self, album_key, section_title, section_type):
        """Process a music album and all its tracks"""
        data = self.make_request(album_key)
        if not data:
            return
            
        # Get all tracks in this album
        tracks = data.get("MediaContainer", {}).get("Metadata", [])
        for track in tracks:
            duration = track.get("duration", 0)
            if duration:
                self.total_duration += duration
                self.media_counts["tracks"] += 1
                self.library_stats[section_title]["count"] += 1
                self.library_stats[section_title]["duration"] += duration
                self.library_stats[section_title]["type"] = section_type
    
    def calculate_total_duration(self):
        """Calculate the total duration of all media in the Plex server"""
        sections = self.get_sections()
        if not sections:
            print("No library sections found or couldn't connect to Plex server.")
            return False
            
        print(f"Found {len(sections)} library sections.")
        
        for section in sections:
            self.process_section(section)
            
        return True
    
    def format_duration(self, milliseconds):
        """Format milliseconds into human-readable time"""
        seconds = milliseconds / 1000
        return str(timedelta(seconds=seconds))
    
    def print_summary(self):
        """Print a summary of all media and their total duration"""
        if TABULATE_AVAILABLE:
            if self.group_by == "type":
                table = [
                    ["Movies", self.media_counts["movies"]],
                    ["TV Episodes", self.media_counts["episodes"]],
                    ["Music Tracks", self.media_counts["tracks"]],
                    ["Other Media", self.media_counts["other"]],
                    ["Total", sum(self.media_counts.values())]
                ]
                print("\n=== MEDIA LIBRARY SUMMARY (by Type) ===")
                print(tabulate(table, headers=["Category", "Count"], tablefmt="github"))
            else:
                table = []
                total = 0
                for lib, stats in self.library_stats.items():
                    table.append([lib, stats["type"], stats["count"], self.format_duration(stats["duration"])])
                    total += stats["count"]
                table.append(["Total", "", total, ""])
                print("\n=== MEDIA LIBRARY SUMMARY (by Library Name) ===")
                print(tabulate(table, headers=["Library Name", "Type", "Count", "Duration"], tablefmt="github"))
        else:
            # Fallback: use string formatting for a readable table
            if self.group_by == "type":
                print("\n=== MEDIA LIBRARY SUMMARY (by Type) ===")
                print(f"{'Category':<15} {'Count':>10}")
                print("-" * 27)
                print(f"{'Movies':<15} {self.media_counts['movies']:>10}")
                print(f"{'TV Episodes':<15} {self.media_counts['episodes']:>10}")
                print(f"{'Music Tracks':<15} {self.media_counts['tracks']:>10}")
                print(f"{'Other Media':<15} {self.media_counts['other']:>10}")
                print("-" * 27)
                print(f"{'Total':<15} {sum(self.media_counts.values()):>10}")
            else:
                print("\n=== MEDIA LIBRARY SUMMARY (by Library Name) ===")
                print(f"{'Library Name':<25} {'Type':<10} {'Count':>8} {'Duration':>20}")
                print("-" * 65)
                total = 0
                for lib, stats in self.library_stats.items():
                    print(f"{lib:<25} {stats['type']:<10} {stats['count']:>8} {self.format_duration(stats['duration']):>20}")
                    total += stats['count']
                print("-" * 65)
                print(f"{'Total':<25} {'':<10} {total:>8}")
        print("\n=== TOTAL DURATION ===")
        total_seconds = self.total_duration / 1000
        days = total_seconds // 86400
        remaining = total_seconds % 86400
        hours = remaining // 3600
        remaining %= 3600
        minutes = remaining // 60
        seconds = remaining % 60
        print(f"Total Duration: {self.format_duration(self.total_duration)}")
        print(f"That's approximately {int(days)} days, {int(hours)} hours, {int(minutes)} minutes, and {int(seconds)} seconds of content!")
        if days > 0:
            print(f"\nIf you watched/listened 8 hours per day:")
            continuous_days = days + (hours / 24) + (minutes / 1440) + (seconds / 86400)
            viewing_days = continuous_days * 3  # Assuming 8 hours per day (24/8 = 3)
            print(f"It would take you about {int(viewing_days)} days to go through your entire library.")
        print("\nThank you for using Plex Media Calculator!")

def main():
    print("Plex Media Duration Calculator")
    print("==============================")
    
    calculator = PlexMediaCalculator()
    
    print("Connecting to Plex server...")
    if calculator.calculate_total_duration():
        calculator.print_summary()
    else:
        print("Failed to calculate media duration. Please check your Plex server connection.")

if __name__ == "__main__":
    main()