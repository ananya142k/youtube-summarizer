from flask import Flask, request, jsonify
from utils import get_video_metadata, download_audio, summarize_text
import os
import asyncio
from deepgram import Deepgram

app = Flask(__name__, static_url_path='/frontend', static_folder='frontend')

DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY', 'YOUR_DEEPGRAM_API_KEY')
PARAMS = {'punctuate': True, 'tier': 'enhanced'}

async def transcribe_audio(file_path):
    deepgram = Deepgram(DEEPGRAM_API_KEY)
    print("Currently transcribing", file_path)

    with open(file_path, 'rb') as audio:
        source = {'buffer': audio, 'mimetype': 'audio/mp3'}
        response = await deepgram.transcription.prerecorded(source, PARAMS)
        return response

@app.route('/process', methods=['POST'])
def process_video():
    video_url = request.json.get('url')
    
    if not video_url:
        return jsonify({'error': 'No URL provided'}), 400

    video_id = extract_video_id(video_url)
    if not video_id:
        return jsonify({'error': 'Invalid YouTube URL'}), 400

    metadata = get_video_metadata(video_id)
    if not metadata:
        return jsonify({'error': 'Video metadata not found'}), 404

    download_status = download_audio(video_url)
    if download_status['status'] == 'error':
        return jsonify({'error': download_status['message']}), 500

    transcription_response = asyncio.run(transcribe_audio(download_status['audio_file']))

    # Extract transcription from the response
    transcript = transcription_response.get('results', {}).get('channels', [{}])[0].get('alternatives', [{}])[0].get('transcript', '')

    # Summarize the transcription using GPT
    summary = summarize_text(transcript)

    return jsonify({'metadata': metadata, 'transcription': transcript, 'summary': summary}), 200

def extract_video_id(url):
    if 'youtu.be/' in url:
        return url.split('youtu.be/')[1].split('?')[0]
    elif 'v=' in url:
        return url.split('v=')[1].split('&')[0]
    else:
        return None

if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    app.run(debug=True)
