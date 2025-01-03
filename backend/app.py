from flask import Flask, request, jsonify, send_from_directory
from backend.utils import get_video_metadata, download_audio, summarize_text, transcribe_audio
import asyncio
import os
import logging
from flask_cors import CORS

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__, static_folder='../frontend')
CORS(app)

# Ensure the downloads directory exists
if not os.path.exists('/tmp/downloads'):
    os.makedirs('/tmp/downloads')

@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route("/process", methods=["POST"])
def process_video():
    try:
        video_url = request.json.get("url")
        if not video_url:
            return jsonify({"error": "No URL provided"}), 400

        async def process_async():
            metadata = get_video_metadata(video_url)
            if not metadata:
                return jsonify({"error": "Video metadata not found"}), 404

            downloaded_audio = await download_audio(video_url)
            if downloaded_audio["status"] == "error":
                return jsonify({"error": downloaded_audio["message"]}), 500

            transcription_response = await transcribe_audio(downloaded_audio["audio_file"])
            if transcription_response["status"] == "error":
                return jsonify({"error": transcription_response["message"]}), 500

            transcript = transcription_response.get("transcript", "")
            summary = summarize_text(transcript)

            return jsonify({
                "metadata": metadata,
                "transcription": transcript,
                "summary": summary,
            }), 200

        return asyncio.run(process_async())

    except Exception as e:
        logging.exception(f"An unexpected error occurred: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)