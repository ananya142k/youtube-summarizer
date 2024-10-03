from googleapiclient.discovery import build
from pytube import YouTube
import deepgram 
import os
import openai

API_KEY = os.getenv('YOUTUBE_API_KEY', 'YOUR_YOUTUBE_API_KEY')
youtube = build('youtube', 'v3', developerKey=API_KEY)
openai.api_key = os.getenv('OPENAI_API_KEY', 'YOUR_OPENAI_API_KEY')


def download_audio(video_url):
    yt = YouTube(video_url)
    audio_stream = yt.streams.filter(only_audio=True).first()
    audio_file = audio_stream.download(output_path='downloads')
        
    base, ext = os.path.splitext(audio_file)
    new_file = f"{base}.mp3"
    os.rename(audio_file, new_file)

    return {'status': 'success', 'audio_file': new_file}

    