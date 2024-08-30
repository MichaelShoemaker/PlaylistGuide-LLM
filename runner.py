import os
import os.path
import re
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

def create_timestamp_dicts(video_id, video_metadata, timecodes):
    """
    Creates a list of dictionaries for each timecode, including title, timecode, text, description, and link.
    """
    base_url = f"https://www.youtube.com/watch?v={video_id}"
    
    timestamp_dicts = []

    for time_str, text in timecodes:
        parts = time_str.split(":")
        if len(parts) == 2:
            minutes, seconds = map(int, parts)
            time_in_seconds = minutes * 60 + seconds
        elif len(parts) == 3:
            hours, minutes, seconds = map(int, parts)
            time_in_seconds = hours * 3600 + minutes * 60 + seconds
        else:
            continue
        
        link = f"{base_url}&t={time_in_seconds}s"
        
        timestamp_dict = {
            'title': video_metadata['title'],
            'timecode': time_str,
            'text': text,
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
        
        timestamp_dicts = create_timestamp_dicts(video_id, video_metadata, timecodes)
        
        all_timestamps.extend(timestamp_dicts)

    return all_timestamps

# Example usage
api_key = API_KEY  # Replace with your actual API key
playlist_id = 'PL3MmuxUbc_hIB4fSqLy_0AfTjVLpgjV3R'  # Replace with your actual playlist ID

# Get information and timestamps for the entire playlist
playlist_timestamps = get_playlist_info_and_timestamps(api_key, playlist_id)


with open('transcripts_metadata_records.pkl', 'wb') as outfile:
    pickle.dump(playlist_timestamps, outfile)