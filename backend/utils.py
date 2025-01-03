import os
import logging
import aiohttp
import cohere
from deepgram import Deepgram
from dotenv import load_dotenv
from googleapiclient.discovery import build
import yt_dlp
import random

load_dotenv()
deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
cohere_api_key = os.getenv("COHERE_API_KEY")
youtube_api_key = os.getenv("YOUTUBE_API_KEY")

if not all([deepgram_api_key, cohere_api_key, youtube_api_key]):
    raise ValueError("Missing required API keys")

youtube = build('youtube', 'v3', developerKey=youtube_api_key)
co = cohere.Client(cohere_api_key)

DOWNLOADS_FOLDER = "/tmp/downloads"
if not os.path.exists(DOWNLOADS_FOLDER):
    os.makedirs(DOWNLOADS_FOLDER)

async def download_audio(video_url):
    try:
        # List of common user agents
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36'
        ]

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(DOWNLOADS_FOLDER, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'http_headers': {
                'User-Agent': random.choice(user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            },
            'extractor_retries': 5,
            'file_access_retries': 5,
            'fragment_retries': 5,
            'skip_download_archive': True,
            'rm_cachedir': True
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            # Force IP v4 and update cookies
            ydl.params['source_address'] = '0.0.0.0'
            
            info = ydl.extract_info(video_url, download=True)
            audio_file_path = os.path.join(
                DOWNLOADS_FOLDER, 
                f"{sanitize_filename(info['title'])}.mp3"
            )
            
            if os.path.exists(audio_file_path):
                return {"status": "success", "audio_file": audio_file_path}
            return {"status": "error", "message": "Audio file download failed."}

    except Exception as e:
        logging.error(f"Failed to download audio from {video_url}: {e}")
        return {"status": "error", "message": str(e)}


async def transcribe_audio(file_path):
    try:
        deepgram = Deepgram(deepgram_api_key)

        async with aiohttp.ClientSession() as session:
            with open(file_path, "rb") as audio:
                source = {"buffer": audio.read(), "mimetype": "audio/mp3"}
                response = await deepgram.transcription.prerecorded(
                    source,
                    {"smart_format": True, "model": "nova-2", "punctuate": True}
                )

        await delete_file(file_path)
        
        transcript = response["results"]["channels"][0]["alternatives"][0]["transcript"]
        return {"status": "success", "transcript": transcript}

    except Exception as e:
        logging.error(f"Transcription error: {e}")
        await delete_file(file_path)
        return {"status": "error", "message": str(e)}

async def delete_file(file_path):
    """Safely delete a file."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.info(f"Deleted file: {file_path}")
    except Exception as e:
        logging.error(f"Error deleting file {file_path}: {e}")


def get_video_metadata(video_url):
    """Fetch metadata using YouTube Data API."""
    try:
        # More robust URL parsing
        video_id = None
        if 'youtu.be' in video_url:
            video_id = video_url.split('/')[-1].split('?')[0]
        elif 'youtube.com' in video_url:
            if 'v=' in video_url:
                video_id = video_url.split('v=')[1].split('&')[0]
            elif 'embed/' in video_url:
                video_id = video_url.split('embed/')[1].split('?')[0]
        
        if not video_id:
            raise ValueError("Invalid YouTube URL")

        request = youtube.videos().list(
            part="snippet,statistics",
            id=video_id
        )
        response = request.execute()

        if not response['items']:
            return None

        video_data = response['items'][0]
        return {
            'title': video_data['snippet']['title'],
            'description': video_data['snippet']['description'],
            'thumbnail': video_data['snippet']['thumbnails']['high']['url'],
            'viewCount': video_data['statistics']['viewCount'],
            'likeCount': video_data['statistics'].get('likeCount', 0),
            'publishedAt': video_data['snippet']['publishedAt']
        }

    except Exception as e:
        logging.error(f"Error fetching metadata: {e}")
        return None
    
def sanitize_filename(filename):
    """Sanitize the filename to avoid issues with invalid characters."""
    return "".join(
        char for char in filename if char.isalnum() or char in (" ", ".", "_")
    ).rstrip()


def summarize_text(text):
    """Summarize text using Cohere's free tier."""
    try:
        response = co.summarize(
            text=text, length="medium", format="paragraph", temperature=0.3
        )
        return response.summary
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        return "Summary could not be generated."