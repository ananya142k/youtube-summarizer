import os
import logging
import aiohttp
import cohere
from pytubefix import YouTube
from deepgram import Deepgram
from dotenv import load_dotenv
from collections import Counter
import re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import json
import base64

# Load environment variables
load_dotenv()
deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
cohere_api_key = os.getenv("COHERE_API_KEY")
youtube_api_key = os.getenv("YOUTUBE_API_KEY")

# Initialize clients
co = cohere.Client(cohere_api_key)
youtube = build('youtube', 'v3', developerKey=youtube_api_key)

def get_youtube_player_data(video_url):
    """Get YouTube video data using the API."""
    try:
        video_id = extract_video_id(video_url)
        if not video_id:
            return {"error": "Invalid YouTube URL"}

        request = youtube.videos().list(
            part="player,contentDetails",
            id=video_id
        )
        response = request.execute()

        if not response["items"]:
            return {"error": "Video not found"}

        return {
            "video_id": video_id,
            "embed_html": response["items"][0]["player"]["embedHtml"],
            "duration": response["items"][0]["contentDetails"]["duration"]
        }
    except Exception as e:
        logging.error(f"Error fetching YouTube data: {e}")
        return {"error": str(e)}

def extract_video_id(url):
    """Extract YouTube video ID from URL."""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_word_frequency(text, min_length=4, top_n=50):
    """Generate word frequency data for visualization."""
    words = re.findall(r'\b\w+\b', text.lower())
    words = [word for word in words if len(word) >= min_length]
    word_counts = Counter(words)
    
    # Remove common stop words
    stop_words = {'this', 'that', 'have', 'what', 'with', 'from', 'they'}
    for word in stop_words:
        word_counts.pop(word, None)
    
    return dict(word_counts.most_common(top_n))

def generate_srt_file(transcript, title):
    """Generate SRT file format based on sentences."""
    if not os.path.exists('exports'):
        os.makedirs('exports')

    # Sanitize the filename
    base_filename = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
    
    # Split transcript into sentences
    sentences = re.split(r'(?<=[.!?])\s+', transcript)
    
    srt_filename = f"{base_filename}.srt"
    srt_path = os.path.join('exports', srt_filename)
    
    avg_words_per_second = 2.5  # Average speaking rate
    current_time = 0
    
    with open(srt_path, 'w', encoding='utf-8') as f:
        for i, sentence in enumerate(sentences, 1):
            # Calculate duration based on word count
            words = len(sentence.split())
            duration = words / avg_words_per_second
            
            start_time = format_srt_time(current_time)
            end_time = format_srt_time(current_time + duration)
            
            f.write(f"{i}\n{start_time} --> {end_time}\n{sentence.strip()}\n\n")
            
            current_time += duration
    
    return srt_filename

def format_srt_time(seconds):
    """Format time for SRT file."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msecs = int((seconds * 1000) % 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{msecs:03d}"

async def download_audio(video_url):
    """Download audio from YouTube video."""
    downloads_folder = "downloads"
    if not os.path.exists(downloads_folder):
        os.makedirs(downloads_folder)

    try:
        yt = YouTube(video_url)
        audio_stream = yt.streams.get_audio_only()

        audio_file_name = sanitize_filename(yt.title)
        audio_file_path = os.path.join(downloads_folder, f"{audio_file_name}.mp3")

        audio_stream.download(
            output_path=downloads_folder, filename=f"{audio_file_name}.mp3"
        )

        if os.path.exists(audio_file_path):
            return {"status": "success", "audio_file": audio_file_path}
        else:
            return {"status": "error", "message": "Audio file download failed."}

    except Exception as e:
        logging.error(f"Failed to download audio from {video_url}: {e}")
        return {"status": "error", "message": str(e)}

async def transcribe_audio(file_path):
    """Transcribe audio using Deepgram."""
    try:
        if not deepgram_api_key:
            return {"status": "error", "message": "Deepgram API key not provided"}

        deepgram = Deepgram(deepgram_api_key)

        async with aiohttp.ClientSession() as session:
            with open(file_path, "rb") as audio:
                source = {"buffer": audio.read(), "mimetype": "audio/mp3"}

                response = await deepgram.transcription.prerecorded(
                    source, {"smart_format": True, "model": "nova-2", "punctuate": True}
                )

        # Delete the audio file after transcription
        await delete_file(file_path)

        transcript = response["results"]["channels"][0]["alternatives"][0]["transcript"]
        return {
            "status": "success",
            "channel": {"alternatives": [{"transcript": transcript}]},
        }

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
    """Fetch metadata for a YouTube video."""
    try:
        yt = YouTube(video_url)
        metadata = {
            "title": yt.title,
            "description": yt.description,
            "thumbnail": yt.thumbnail_url,
            "author": yt.author,
            "publish_date": str(yt.publish_date),
            "views": yt.views,
            "length": yt.length
        }
        return metadata

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
            text=text,
            length="medium",
            format="paragraph",
            temperature=0.3
        )
        return response.summary
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        return "Summary could not be generated."