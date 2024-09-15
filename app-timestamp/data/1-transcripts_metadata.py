"""
This script retrieves metadata and timestamps from YouTube videos within a specific playlist and saves the data to a pickle file.

The script performs the following tasks:
1. Loads the YouTube API key from environment variables using `dotenv`.
2. Connects to the YouTube API using the `googleapiclient.discovery` module.
3. Retrieves the list of video IDs from a specified YouTube playlist.
4. For each video in the playlist:
   - Fetches video metadata (title and description).
   - Extracts timecodes and their associated descriptions from the video description using regex.
   - Converts the extracted timecodes into clickable YouTube links at the corresponding timestamps.
5. Compiles the video metadata, timecodes, and clickable links into a list of dictionaries.
6. Saves the compiled data into a pickle file named `transcripts_metadata_records.pkl` for later use.

Functions:
- `get_videos_in_playlist(api_key, playlist_id)`: Fetches all video IDs in a given playlist.
- `get_video_metadata(api_key, video_id)`: Retrieves metadata for a specific video.
- `extract_timecodes_and_descriptions(description)`: Uses regex to extract timecodes and associated descriptions from the video description.
- `create_timestamp_dicts(video_id, video_metadata, timecodes)`: Creates a dictionary for each timecode with video metadata and clickable timestamps.
- `get_playlist_info_and_timestamps(api_key, playlist_id)`: Combines all previous functions to generate a list of timestamp dictionaries for each video in a playlist.

Finally, the compiled data is saved in a pickle file for persistence.

Example:
To use the script, replace `API_KEY` with your YouTube API key and `playlist_id` with the desired playlist's ID.
"""

import os
import re
import sys
import pickle
from dotenv import load_dotenv
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi

load_dotenv()
API_KEY = os.getenv("YouTube_API_KEY")

youtube = build('youtube', 'v3', developerKey=API_KEY)

def get_videos_in_playlist(api_key, playlist_id):
    """
    Retrieves a list of video IDs from a given YouTube playlist ID.
    """
    youtube = build('youtube', 'v3', developerKey=api_key)
    video_ids = []

    request = youtube.playlistItems().list(
        part='contentDetails',
        playlistId=playlist_id,
        maxResults=50  # Max results per API call
    )

    while request:
        response = request.execute()

        for item in response.get('items', []):
            video_ids.append(item['contentDetails']['videoId'])

        request = youtube.playlistItems().list_next(request, response)
    if os.path.isfile('processed.txt'):
        historical = set()
        with open('processed.txt','r') as infile:
            for id in infile:
                historical.add(id)
        return list(set(video_ids) - historical)
    
    return video_ids

def get_video_metadata(api_key, video_id):
    """
    Retrieves metadata for a given YouTube video ID.
    """
    youtube = build('youtube', 'v3', developerKey=api_key)
    
    request = youtube.videos().list(
        part='snippet',
        id=video_id
    )
    
    response = request.execute()
    
    if 'items' in response and len(response['items']) > 0:
        return response['items'][0]
    else:
        return None

def extract_timecodes_and_descriptions(description):
    """
    Extracts timecodes and their associated descriptions from the video description using regex.
    """
    timecode_pattern = r"(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)"
    
    matches = re.findall(timecode_pattern, description)
    
    timecodes = [(match[0], match[1].strip()) for match in matches]
    
    return timecodes

def get_transcript(video_id):
    """
    Retrieves the transcript for a given YouTube video ID.
    """
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript
    except Exception as e:
        print(f"Could not retrieve transcript for video ID: {video_id} - {e}")
        return []

def convert_time_to_seconds(time_str):
    """
    Converts a time string (e.g., "2:34" or "1:23:45") to seconds.
    """
    if isinstance(time_str, (int, float)):
        return float(time_str)
    
    parts = time_str.split(":")
    if len(parts) == 2:
        minutes, seconds = map(int, parts)
        return minutes * 60 + seconds
    elif len(parts) == 3:
        hours, minutes, seconds = map(int, parts)
        return hours * 3600 + minutes * 60 + seconds
    return 0

def create_timestamp_dicts(video_id, video_metadata, timecodes, transcript):
    """
    Creates a list of dictionaries for each timecode, including title, timecode, text, description, and link.
    """
    base_url = f"https://www.youtube.com/watch?v={video_id}"
    
    transcript_texts = [
        {'start': float(item['start']), 'text': item['text']} for item in transcript
    ]
    
    timestamp_dicts = []
    
    # If no timecodes are found, use the entire transcript with a default timecode
    if not timecodes:
        entire_transcript_text = ' '.join([item['text'] for item in transcript_texts])
        timestamp_dict = {
            'vid_id': video_id,
            'title': video_metadata['title'],
            'timecode': '00:00',
            'text': entire_transcript_text,
            'timecode_text': 'Full Transcript',
            'description': video_metadata['description'].split('\n\n')[0],
            'link': base_url
        }
        timestamp_dicts.append(timestamp_dict)
    else:
        for i, (time_str, timecode_text) in enumerate(timecodes):
            start_time = convert_time_to_seconds(time_str)
            if i < len(timecodes) - 1:
                end_time = convert_time_to_seconds(timecodes[i + 1][0])
            else:
                end_time = float('inf')
            
            # Get the transcript text between start_time and end_time
            transcript_text = ' '.join([
                item['text'] for item in transcript_texts 
                if start_time <= item['start'] < end_time
            ])
            
            link = f"{base_url}&t={start_time}s"
            
            timestamp_dict = {
                'vid_id': video_id,
                'title': video_metadata['title'],
                'timecode': time_str,
                'text': transcript_text,
                'timecode_text': timecode_text,
                'description': video_metadata['description'].split('\n\n')[0],
                'link': link
            }
            
            timestamp_dicts.append(timestamp_dict)
    
    return timestamp_dicts

def get_playlist_info_and_timestamps(api_key, playlist_id):
    """
    Main function that retrieves video metadata and creates timestamp dictionaries for each video in a playlist.
    """
    video_ids = get_videos_in_playlist(api_key, playlist_id)

    if len(video_ids) == 0:
        print("There are no new videos to process")
        sys.exit(1)
    
    all_timestamps = []

    for video_id in video_ids:
        video_metadata_response = get_video_metadata(api_key, video_id)
        
        if not video_metadata_response:
            print(f"No metadata found for video ID: {video_id}")
            continue
        
        video_metadata = {
            'title': video_metadata_response['snippet']['title'],
            'description': video_metadata_response['snippet']['description']
        }

        timecodes = extract_timecodes_and_descriptions(video_metadata['description'])
        transcript = get_transcript(video_id)
        
        timestamp_dicts = create_timestamp_dicts(video_id, video_metadata, timecodes, transcript)
        
        all_timestamps.extend(timestamp_dicts)

    return all_timestamps

# Example usage
api_key = API_KEY  # Replace with your actual API key
playlist_id = 'PL3MmuxUbc_hIB4fSqLy_0AfTjVLpgjV3R'  # Replace with your actual playlist ID

# Get information and timestamps for the entire playlist
playlist_timestamps = get_playlist_info_and_timestamps(api_key, playlist_id)


with open('transcripts_metadata_records.pkl', 'wb') as outfile:
    pickle.dump(playlist_timestamps, outfile)

# TODO - read in old pickle file if exists and just add new records
# processed = set()
# for i in playlist_timestamps:
#     processed.add(i['vid_id'])

# if os.path.isfile('processed.txt'):
#     with open('processed.txt','a') as infile:
#         for rec in list(processed):
#             infile.writelines(rec+'\n')
# else:
#     with open('processed.txt','w') as infile:
#         for rec in list(processed):
#             infile.writelines(rec+'\n')