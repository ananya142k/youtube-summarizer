from googleapiclient.discovery import build
from pytube import YouTube
import os
import openai

API_KEY = os.getenv('YOUTUBE_API_KEY', 'YOUR_YOUTUBE_API_KEY')
openai.api_key = os.getenv('OPENAI_API_KEY', 'YOUR_OPENAI_API_KEY')
youtube = build('youtube', 'v3', developerKey=API_KEY)

def download_audio(video_url):
    yt = YouTube(video_url)
    audio_stream = yt.streams.filter(only_audio=True).first()
    audio_file = audio_stream.download(output_path='downloads')
        
    base, ext = os.path.splitext(audio_file)
    new_file = f"{base}.mp3"
    os.rename(audio_file, new_file)

    return {'status': 'success', 'audio_file': new_file}

def get_video_metadata(video_id):
    request = youtube.videos().list(
        part='snippet',
        id=video_id
    )
    response = request.execute()
    
    if response['items']:
        video_data = response['items'][0]['snippet']
        return {
            'title': video_data['title'],
            'description': video_data['description'],
            'thumbnail': video_data['thumbnails']['high']['url']
        }
    else:
        return None

def summarize_text(text):
    response = openai.Completion.create(
        engine="gpt-4",  
        prompt=f"Summarize the following transcription:\n\n{text}",
        max_tokens=150,
        temperature=0.7
    )
    
    summary = response.choices[0].text.strip()
    return summary
