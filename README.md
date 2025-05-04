# Plex Media Duration Calculator

## Overview
This Python script calculates the total duration of all media in your Plex library, including movies, TV shows, and music. It answers the question: "If I watched and listened to everything in my Plex library, how long would it take?"

## Features
- Calculates total duration of all media content in your Plex server
- Breaks down content by type (movies, TV episodes, music tracks)
- Provides continuous playback duration (24-hour) and realistic viewing duration (8-hour day)
- Saves configuration for easy future use
- Works with all standard Plex libraries

## Requirements
- Python 3.6 or higher
- A Plex Media Server
- Your Plex authentication token

## Installation

### Step 1: Clone or download the script
Save the `plex_duration_calculator.py` script to your desired location.

### Step 2: Set up a virtual environment (recommended)

#### For Windows:
```
python -m venv plex_env
plex_env\Scripts\activate
```

#### For macOS/Linux:
```
python3 -m venv plex_env
source plex_env/bin/activate
```

### Step 3: Install dependencies
```
pip install -r requirements.txt
```

## Usage

### Running the script
```