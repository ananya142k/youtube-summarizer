from flask import Flask, request, jsonify
from utils import get_video_metadata, download_audio, summarize_text
import os
import asyncio
import json
from deepgram import Deepgram

app = Flask(__name__, static_url_path='/frontend', static_folder='frontend')

DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY', 'YOUR_DEEPGRAM_API_KEY')
PARAMS = {'punctuate': True, 'tier': 'enhanced'}


@app.route('/process', methods=['POST'])
def process_video():
    video_url = request.json.get('url')
    download_audio(video_url)

 
if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    app.run(debug=True)
