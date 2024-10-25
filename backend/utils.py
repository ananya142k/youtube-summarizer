from pytubefix import YouTube
from deepgram import Deepgram
import openai
import os
import logging
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")  # Ensure your API key is stored in .env

# Parameters for Deepgram transcription
PARAMS = {'punctuate': True, 'tier': 'enhanced'}

def download_audio(video_url):
    """Download audio from YouTube video."""
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    try:
        yt = YouTube(video_url)
        audio_stream = yt.streams.filter(only_audio=True).first()
        audio_file_path = audio_stream.download(output_path='downloads')

        if os.path.exists(audio_file_path):
            return {'status': 'success', 'audio_file': audio_file_path}
        else:
            return {'status': 'error', 'message': 'Audio file download failed.'}

    except Exception as e:
        logging.error(f"Failed to download audio from {video_url}: {e}")
        return {'status': 'error', 'message': str(e)}

async def transcribe_audio(file_path):
    """Transcribe audio using Deepgram."""
    deepgram = Deepgram(os.getenv('DEEPGRAM_API_KEY'))  # Ensure to set this environment variable
    print("Currently transcribing", file_path)

    with open(file_path, 'rb') as audio:
        source = {'buffer': audio, 'mimetype': 'audio/mp3'}
        response = await deepgram.transcription.prerecorded(source, PARAMS)
        return response

def get_video_metadata(video_url):
    """Fetch metadata for a YouTube video."""
    try:
        yt = YouTube(video_url)
        metadata = {
            'title': yt.title,
            'description': yt.description,
            'thumbnail': yt.thumbnail_url
        }
        return metadata

    except Exception as e:
        logging.error(f"Error fetching metadata: {e}")
        return None

def generate_summarizer(
    max_tokens=100,
    temperature=0.7,
    top_p=0.5,
    frequency_penalty=0.5,
    prompt="",
    person_type="general",
):
    """Generate a summary using OpenAI API."""
    res = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant for text summarization.",
            },
            {
                "role": "user",
                "content": f"Summarize this for a {person_type}: {prompt}",
            },
        ],
    )
    return res["choices"][0]["message"]["content"]

def summarize_text(text, person_type="general"):
    """Generate a summary of the provided text using OpenAI."""
    try:
        summary = generate_summarizer(prompt=text, person_type=person_type)
        return summary
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        return "Summary could not be generated."
