# PlaylistGuide-LLM
An LLM Chatbot which assists the user with answering questions about and finding locations of content in a Youtube Playlist

## Problem Statement
Playlists can be quite long and finding the exact location of content can be tedious. This project aims to assist users with finding the locations (video and timestamp) of specific content and be able to answer questions about the content in a given playlist.

## Project Overview
There are three main directories of interest in this project
* <b>app</b> - This is the directory where the transcript RAG/LLM Application is
* <b>transcript_pulls</b> - This directory contains research for several ways in which the transcripts were attempted to be pulled
* <b>evaluation</b> - This directory contains the generation of a ground truth data set as well as Hit Rate and MRR Evaluations


## Walkthrough Video
TODO

## Steps to reproduce
Optional - log into a GCP account and search for YouTube</br>
![API Search](./images/YouTubeAPISearch.png)</br>

You may need to Enable the API. Once enabled you can then click Manage</br>
![API Search](./images/YouTubeAPIManage.png)</br>

Click the credentials button on the left and then + Create Credentials</br>
![API Search](./images/CreateCredentials.png)</br>

# Create a .env File
### PostgreSQL
POSTGRES_USER=postgres_user
POSTGRES_PASSWORD=postgres_password
POSTGRES_DB=user_feedback

### pgAdmin
PGADMIN_DEFAULT_EMAIL=admin@example.com
PGADMIN_DEFAULT_PASSWORD=admin_password

### OpenAI API Key
OPENAI_API_KEY=your_openai_api_key

### YouTube API Key
YouTube_API_KEY=your_youtube_api_key

