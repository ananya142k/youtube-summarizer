document.addEventListener('DOMContentLoaded', () => {
    const videoForm = document.getElementById('videoForm');
    const loader = document.getElementById('loader');
    const outputSection = document.getElementById('outputSection');
    const tabs = document.querySelectorAll('.tab-btn');

    function extractTimestamps(transcript) {
        const words = transcript.split(/\s+/);
        const timestamps = [];
        const chunkSize = 60;  // More granular timestamp chunks

        for (let i = 0; i < words.length; i += chunkSize) {
            const chunk = words.slice(i, i + chunkSize).join(' ');
            timestamps.push({
                time: formatTime(i * 0.25),  // Rough time approximation
                text: chunk + '...'
            });
        }

        return timestamps;
    }

    function formatTime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    function formatSummary(summary) {
        const sections = summary.split(/\.\s+/).filter(s => s.trim());
        const formattedSections = sections.map(section =>
            `<div class="summary-section">
                <h4>• ${section.trim()}.</h4>
             </div>`
        );
        return formattedSections.join('');
    }

    function renderTimestamps(timestamps) {
        return timestamps.map(ts =>
            `<div class="timestamp-item">
                <span class="timestamp-time">${ts.time}</span>
                <p class="timestamp-text">${ts.text}</p>
             </div>`
        ).join('');
    }

    // Tab switching functionality
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetId = tab.dataset.tab;

            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            document.getElementById(targetId).classList.add('active');
        });
    });

    videoForm.addEventListener('submit', async function (event) {
        event.preventDefault();

        const videoUrl = document.getElementById('videoUrl').value;

        loader.style.display = 'block';
        outputSection.style.display = 'none';

        try {
            const response = await fetch('/process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ url: videoUrl })
            });

            if (!response.ok) {
                throw new Error(await response.text());
            }

            const data = await response.json();

            // Update video metadata
            document.getElementById('thumbnail').src = data.metadata.thumbnail;
            document.getElementById('videoTitle').textContent = data.metadata.title;
            document.getElementById('videoDescription').textContent =
                data.metadata.description.length > 250
                    ? data.metadata.description.substring(0, 250) + '...'
                    : data.metadata.description;

            // Process and display content
            const timestamps = extractTimestamps(data.transcription);

            document.getElementById('summaryContent').innerHTML = formatSummary(data.summary);
            document.getElementById('transcriptContent').textContent = data.transcription;
            document.getElementById('timestampsContent').innerHTML = renderTimestamps(timestamps);

            // Show output
            loader.style.display = 'none';
            outputSection.style.display = 'block';

        } catch (error) {
            alert(`Error processing video: ${error.message}`);
            loader.style.display = 'none';
        }
    });
});