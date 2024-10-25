document.getElementById('videoForm').addEventListener('submit', async function(event) {
    event.preventDefault();

    const videoUrl = document.getElementById('videoUrl').value;

    const response = await fetch('/process', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ url: videoUrl })
    });

    if (response.ok) {
        const data = await response.json();

        const transcript = data.transcription || 'No transcript available.';
        const summary = data.summary || 'No summary available.';

        document.getElementById('transcript').innerText = transcript;
        document.getElementById('summary').innerText = summary;

        const timestampsList = document.getElementById('timestamps');
        timestampsList.innerHTML = '';

        if (data.results && data.results.channels && data.results.channels[0] &&
            data.results.channels[0].alternatives && data.results.channels[0].alternatives[0].words) {
            const words = data.results.channels[0].alternatives[0].words;
            words.forEach(word => {
                const li = document.createElement('li');
                li.innerHTML = `<a href="#${formatTime(word.start)}">${formatTime(word.start)} - ${word.word}</a>`;
                timestampsList.appendChild(li);
            });
        }

        document.getElementById('outputSection').style.display = 'block';
    } else {
        const errorData = await response.json();
        alert(`Error: ${errorData.error || 'Something went wrong!'}`);
    }
});

function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}
