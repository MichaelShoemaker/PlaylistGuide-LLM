import os
import sys
import pickle
from dotenv import load_dotenv
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi

load_dotenv()
API_KEY = os.getenv("YouTube_API_KEY")


youtube = build('youtube', 'v3', developerKey=API_KEY)

def get_playlist_videos(playlist_id):
    """Retrieve a list of video IDs from a YouTube playlist."""
    videos = []
    next_page_token = None

    while True:
        pl_request = youtube.playlistItems().list(
            part='contentDetails',
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token
        )

        pl_response = pl_request.execute()
        videos += [item['contentDetails']['videoId'] for item in pl_response['items']]
        next_page_token = pl_response.get('nextPageToken')

        if next_page_token is None:
            break

    return videos

def get_video_title(video_id):
    """Retrieve the title of a YouTube video."""
    video_request = youtube.videos().list(
        part='snippet',
        id=video_id
    )

    video_response = video_request.execute()
    if 'items' in video_response and video_response['items']:
        return video_response['items'][0]['snippet']['title']
    else:
        print(f"Could not retrieve title for video ID: {video_id}")
        return None

def get_video_transcript(video_id):
    """Retrieve the transcript of a YouTube video."""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return ' '.join([text['text'] for text in transcript])
    except Exception as e:
        print(f"Could not retrieve transcript for video {video_id}: {e}")
        return None

def get_playlist_transcripts(playlist_id):
    """Create a dictionary with video titles and transcripts from a YouTube playlist."""
    videos = get_playlist_videos(playlist_id)
    transcripts = {}

    for video_id in videos:
        title = get_video_title(video_id)
        if title:
            transcript = get_video_transcript(video_id)
            if transcript:
                transcripts[title] = transcript

    return transcripts






if __name__ == '__main__':
    #Change the playlist_id to use a playlist other than LLM Zoomcamp
    playlist_id = 'PL3MmuxUbc_hIB4fSqLy_0AfTjVLpgjV3R'
    try:
        transcripts = get_playlist_transcripts(playlist_id)
    except Exception as e:
        print("Something went wrong")
        sys.exit(1)

    with open('transcripts.pkl', 'wb') as outfile:
        pickle.dump(transcripts, outfile)