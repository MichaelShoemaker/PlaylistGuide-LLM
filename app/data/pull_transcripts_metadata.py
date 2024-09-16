import os
import re
import sys
import pickle
import hashlib
from dotenv import load_dotenv
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi

load_dotenv()
API_KEY = os.getenv("YouTube_API_KEY")

youtube = build('youtube', 'v3', developerKey=API_KEY)


def get_videos_in_playlist(api_key, playlist_id):
    """
    Retrieves a list of video IDs from a given YouTube playlist ID, skipping those already processed.
    """
    youtube = build('youtube', 'v3', developerKey=api_key)
    video_ids = []

    request = youtube.playlistItems().list(
        part='contentDetails',
        playlistId=playlist_id,
        maxResults=50
    )

    while request:
        response = request.execute()
        for item in response.get('items', []):
            video_ids.append(item['contentDetails']['videoId'])

        request = youtube.playlistItems().list_next(request, response)

    # Check if processed.txt exists and filter out already processed videos
    processed_video_ids = set()
    if os.path.isfile('processed.txt'):
        with open('processed.txt', 'r') as infile:
            processed_video_ids = {line.strip() for line in infile}

    # Return only new video IDs
    return [vid_id for vid_id in video_ids if vid_id not in processed_video_ids]


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
    return [(match[0], match[1].strip()) for match in matches]


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


def gen_ids(data):
    """
    Generates a unique ID for each record based on the video ID and timecode.
    """
    for rec in data:
        unique_id = rec['vid_id'].strip() + rec['timecode'].strip()
        hash_object = hashlib.md5(unique_id.encode())
        hash_hex = hash_object.hexdigest()
        rec['id'] = hash_hex
    return data


def add_text_vector(data):
    """
    Adds a 'text_vector' field to each record by concatenating title, text, and description.
    """
    for rec in data:
        rec['text_vector'] = f"{rec['title']} {rec['text']} {rec['description']}"
    return data


def get_playlist_info_and_timestamps(api_key, playlist_id):
    """
    Main function that retrieves video metadata and creates timestamp dictionaries for each video in a playlist.
    """
    video_ids = get_videos_in_playlist(api_key, playlist_id)

    if len(video_ids) == 0:
        print("There are no new videos to process.")
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

    # Generate unique IDs for each record
    all_timestamps = gen_ids(all_timestamps)

    # Add text vector to each record
    all_timestamps = add_text_vector(all_timestamps)

    return all_timestamps


# Example usage
api_key = API_KEY
playlist_id = 'PL3MmuxUbc_hIB4fSqLy_0AfTjVLpgjV3R'

# Load existing pickle data if available
if os.path.isfile('transcripts_metadata_records.pkl'):
    with open('transcripts_metadata_records.pkl', 'rb') as infile:
        all_timestamps = pickle.load(infile)
else:
    all_timestamps = []

# Get information and timestamps for new videos in the playlist
new_timestamps = get_playlist_info_and_timestamps(api_key, playlist_id)

# Append new timestamps to existing ones
all_timestamps.extend(new_timestamps)

# Write updated records back to the pickle file
with open('transcripts_metadata_records.pkl', 'wb') as outfile:
    pickle.dump(all_timestamps, outfile)

# Update processed.txt with new video IDs
with open('processed.txt', 'a') as processed_file:
    for video in new_timestamps:
        processed_file.write(video['vid_id'] + '\n')
