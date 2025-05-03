#!/usr/bin/env python3
import requests
import time
import configparser
import os
import sys
from datetime import timedelta

class PlexMediaCalculator:
    def __init__(self, server_url=None, token=None, config_file="plex_config.ini"):
        self.config_file = config_file
        self.server_url = server_url
        self.token = token
        self.total_duration = 0  # duration in milliseconds
        self.media_counts = {
            "movies": 0,
            "episodes": 0,
            "tracks": 0,
            "other": 0
        }
        
        # Load configuration if not provided
        if not server_url or not token:
            self.load_config()
            
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
                
            elif section_type == "show":
                # For shows, we need to get all episodes
                show_key = item.get("key")
                self.process_show(show_key)
                
            elif section_type == "artist":
                # For music, we need to get all albums and tracks
                artist_key = item.get("key")
                self.process_artist(artist_key)
                
            else:
                # Handle other media types
                duration = item.get("duration", 0)
                if duration:
                    section_duration += duration
                    section_count += 1
                    self.media_counts["other"] += 1
        
        if section_type == "movie":
            self.total_duration += section_duration
            print(f"  Found {section_count} movies with total duration: {self.format_duration(section_duration)}")
    
    def process_show(self, show_key):
        """Process a TV show and all its episodes"""
        data = self.make_request(show_key)
        if not data:
            return
            
        # Get all seasons
        seasons = data.get("MediaContainer", {}).get("Metadata", [])
        for season in seasons:
            season_key = season.get("key")
            self.process_season(season_key)
    
    def process_season(self, season_key):
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
    
    def process_artist(self, artist_key):
        """Process a music artist and all their tracks"""
        data = self.make_request(artist_key)
        if not data:
            return
            
        # Get all albums
        albums = data.get("MediaContainer", {}).get("Metadata", [])
        for album in albums:
            album_key = album.get("key")
            self.process_album(album_key)
    
    def process_album(self, album_key):
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
        print("\n=== MEDIA LIBRARY SUMMARY ===")
        print(f"Movies: {self.media_counts['movies']}")
        print(f"TV Episodes: {self.media_counts['episodes']}")
        print(f"Music Tracks: {self.media_counts['tracks']}")
        print(f"Other Media: {self.media_counts['other']}")
        print(f"Total Items: {sum(self.media_counts.values())}")
        print("\n=== TOTAL DURATION ===")
        
        # Convert to more understandable units
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