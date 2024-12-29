import os
import logging
import aiohttp
import cohere
import yt_dlp
from deepgram import Deepgram
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()
deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
cohere_api_key = os.getenv("COHERE_API_KEY")

# Initialize Cohere client
co = cohere.Client(cohere_api_key)

# Configure yt-dlp
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'quiet': True,
    'no_warnings': True,
}

async def download_audio(video_url):
    """Download audio from YouTube video."""
    downloads_folder = "downloads"
    if not os.path.exists(downloads_folder):
        os.makedirs(downloads_folder)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            audio_file_name = sanitize_filename(info['title'])
            audio_file_path = os.path.join(downloads_folder, f"{audio_file_name}.mp3")
            
            # Update options with output template
            ydl_opts_with_path = {
                **ydl_opts,
                'outtmpl': audio_file_path,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts_with_path) as ydl:
                ydl.download([video_url])

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
        # Attempt to delete file even if transcription fails
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
    """Fetch metadata for a YouTube video using yt-dlp."""
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            metadata = {
                'title': info.get('title'),
                'description': info.get('description', ''),
                'thumbnail': info.get('thumbnail'),
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