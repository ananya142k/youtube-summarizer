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
});jg