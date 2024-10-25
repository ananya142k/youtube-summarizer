from flask import Flask, request, jsonify, send_from_directory
from utils import get_video_metadata, download_audio, summarize_text, transcribe_audio
import asyncio
import os
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__, static_folder='../frontend')

# Route to serve the main index.html
@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

# Route to process the YouTube video and return summary, transcript, etc.
@app.route('/process', methods=['POST'])
def process_video():
    try:
        video_url = request.json.get('url')

        if not video_url:
            return jsonify({'error': 'No URL provided'}), 400

        logging.debug(f"Processing video URL: {video_url}")

        # Directly use the video URL for fetching metadata
        metadata = get_video_metadata(video_url)
        if not metadata:
            return jsonify({'error': 'Video metadata not found'}), 404

        downloaded_audio = download_audio(video_url)
        if downloaded_audio['status'] == 'error':
            logging.error(f"Error downloading audio: {downloaded_audio['message']}")
            return jsonify({'error': downloaded_audio['message']}), 500

        transcription_response = asyncio.run(transcribe_audio(downloaded_audio['audio_file']))
        logging.debug(f"Transcription response: {transcription_response}")

        # Extract transcription from the response
        transcript = transcription_response.get('channel', {}).get('alternatives', [{}])[0].get('transcript', '')
        logging.debug(f"Transcript: {transcript}")

        # Summarize the transcription using GPT
        summary = summarize_text(transcript)
        logging.debug(f"Summary: {summary}")

        return jsonify({'metadata': metadata, 'transcription': transcript, 'summary': summary}), 200

    except Exception as e:
        logging.exception(f"An unexpected error occurred: {e}")
        return jsonify({'error': str(e)}), 500

# Serve static files (CSS, JS)
@app.route('/frontend/<path:path>')
def serve_static_files(path):
    return send_from_directory('../frontend', path)

if __name__ == '__main__':
    app.run(debug=True)
