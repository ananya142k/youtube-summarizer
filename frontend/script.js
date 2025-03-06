document.addEventListener('DOMContentLoaded', () => {
    
    // Initialize YouTube IFrame API
    const tag = document.createElement('script');
    tag.src = "https://www.youtube.com/iframe_api";
    const firstScriptTag = document.getElementsByTagName('script')[0];
    firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);
    
    // Global variables
    let player;
    const videoForm = document.getElementById('videoForm');
    const loader = document.getElementById('loader');
    const outputSection = document.getElementById('outputSection');
    const tabs = document.querySelectorAll('.tab-btn');
    const recentVideos = document.getElementById('recentVideos');
    let wordFrequencyChart = null;
    let currentVideoData = null;

    // Theme handling
    const themeToggle = document.getElementById('themeToggle');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');

    // Description expansion handling
    function cleanupExistingDescription() {
        const description = document.getElementById('videoDescription');
        if (!description) return;

        // Remove any existing expansion elements
        const existingButton = description.parentNode.querySelector('.expand-description');
        const existingFade = description.parentNode.querySelector('.description-fade');
        if (existingButton) existingButton.remove();
        if (existingFade) existingFade.remove();

        // Reset description classes
        description.className = 'description';
    }

    function initializeDescription() {
        // Clean up any existing description elements first
        cleanupExistingDescription();

        const description = document.getElementById('videoDescription');
        if (!description) return;

        const content = description.textContent;
        const isMobile = window.innerWidth <= 768;
        const maxLength = isMobile ? 150 : 300; // Shorter text for mobile

        if (content.length > maxLength) {
            const expandButton = document.createElement('button');
            expandButton.className = 'expand-description';
            expandButton.innerHTML = '<span>Show more</span>';
            expandButton.style.color = document.body.classList.contains('dark-theme') ? '#fff' : '#000';

            const fadeElement = document.createElement('div');
            fadeElement.className = 'description-fade';

            description.parentNode.appendChild(fadeElement);
            description.parentNode.appendChild(expandButton);

            expandButton.addEventListener('click', () => {
                description.classList.toggle('description-expanded');
                fadeElement.style.display = description.classList.contains('description-expanded') ? 'none' : 'block';
                expandButton.innerHTML = description.classList.contains('description-expanded') ?
                    '<span>Show less</span>' : '<span>Show more</span>';
            });
        }
    }

    // Handle resize events for description
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            initializeDescription();
        }, 250);
    });

    // Update description colors when theme changes
    function updateDescriptionTheme(isDark) {
        const expandButton = document.querySelector('.expand-description');
        if (expandButton) {
            expandButton.style.color = isDark ? '#fff' : '#000';
        }
    }

    function setTheme(isDark) {
        document.body.classList.toggle('dark-theme', isDark);
        document.body.classList.toggle('light-theme', !isDark);
        themeToggle.innerHTML = isDark ? '<i class="ri-moon-line"></i>' : '<i class="ri-sun-line"></i>';
        localStorage.setItem('theme', isDark ? 'dark' : 'light');

        // Update chart if it exists
        updateChartTheme(isDark);
        // Update description button color
        updateDescriptionTheme(isDark);
    }

    // Initialize theme
    const savedTheme = localStorage.getItem('theme');
    setTheme(savedTheme === 'dark' || (savedTheme === null && prefersDark.matches));

    themeToggle.addEventListener('click', () => {
        setTheme(!document.body.classList.contains('dark-theme'));
    });

    // Recent videos handling
    function updateRecentVideos(videoData) {
        let recent = JSON.parse(localStorage.getItem('recentVideos') || '[]');
        recent = recent.filter(v => v.id !== videoData.id);
        recent.unshift(videoData);
        recent = recent.slice(0, 6); // Keep only 6 most recent
        localStorage.setItem('recentVideos', JSON.stringify(recent));
        displayRecentVideos();
    }

    function displayRecentVideos() {
        const recent = JSON.parse(localStorage.getItem('recentVideos') || '[]');
        if (recent.length === 0) {
            recentVideos.style.display = 'none';
            return;
        }

        const grid = recentVideos.querySelector('.recent-videos-grid');
        const container = document.createElement('div');
        container.className = 'recent-videos-container';

        const videos = recent.map(video => `
            <div class="recent-video-item" data-url="https://www.youtube.com/watch?v=${video.id}">
                <img src="${video.thumbnail}" alt="${video.title}">
                <div class="recent-video-info">
                    <h4 title="${video.title}">${video.title}</h4>
                </div>
            </div>
        `).join('');

        container.innerHTML = `
            <div class="recent-videos-scroll">
                ${videos}
            </div>
            <button class="scroll-btn scroll-left" aria-label="Scroll left">
                <i class="ri-arrow-left-s-line"></i>
            </button>
            <button class="scroll-btn scroll-right" aria-label="Scroll right">
                <i class="ri-arrow-right-s-line"></i>
            </button>
        `;

        grid.innerHTML = '';
        grid.appendChild(container);

        // Add scroll button handlers
        const scrollContainer = grid.querySelector('.recent-videos-scroll');
        const scrollLeftBtn = grid.querySelector('.scroll-left');
        const scrollRightBtn = grid.querySelector('.scroll-right');

        scrollLeftBtn.addEventListener('click', () => {
            scrollContainer.scrollBy({ left: -200, behavior: 'smooth' });
        });

        scrollRightBtn.addEventListener('click', () => {
            scrollContainer.scrollBy({ left: 200, behavior: 'smooth' });
        });

        // Show/hide scroll buttons based on scroll position
        function updateScrollButtons() {
            const scrollContainer = document.querySelector('.recent-videos-scroll');
            const scrollLeftBtn = document.querySelector('.scroll-left');
            const scrollRightBtn = document.querySelector('.scroll-right');

            if (!scrollContainer || !scrollLeftBtn || !scrollRightBtn) return;

            const hasScrollableContent = scrollContainer.scrollWidth > scrollContainer.clientWidth;
            const isAtStart = scrollContainer.scrollLeft <= 0;
            const isAtEnd = scrollContainer.scrollLeft >= (scrollContainer.scrollWidth - scrollContainer.clientWidth - 1);

            scrollLeftBtn.style.display = isAtStart ? 'none' : 'flex';
            scrollRightBtn.style.display = hasScrollableContent && !isAtEnd ? 'flex' : 'none';
        }

        scrollContainer.addEventListener('scroll', updateScrollButtons);
        updateScrollButtons();

        recentVideos.style.display = 'block';
    }

    recentVideos.addEventListener('click', (e) => {
        const videoItem = e.target.closest('.recent-video-item');
        if (videoItem) {
            const videoUrl = videoItem.dataset.url;
            document.getElementById('videoUrl').value = videoUrl;
            videoForm.dispatchEvent(new Event('submit'));
        }
    });

    // Initialize recent videos
    displayRecentVideos();

    function updateSubtitles(data) {
        const subtitlesContent = document.getElementById('subtitlesContent');
        const transcriptContent = document.getElementById('transcriptContent');

        // Always update the transcript tab with the transcription text
        if (data && data.transcription) {
            transcriptContent.textContent = data.transcription;
        } else {
            transcriptContent.textContent = 'No transcript available.';
        }

        // Debugging: Log the subtitles data
        console.log('Subtitles Data:', data.subtitles);

        // Update subtitles tab with timestamped content
        if (data && Array.isArray(data.subtitles) && data.subtitles.length > 0) {
            subtitlesContent.innerHTML = data.subtitles.map(subtitle => {
                // Robust timestamp extraction
                const startTime =
                    subtitle.start_seconds ||
                    subtitle.start ||
                    subtitle.startSeconds ||
                    0;

                const endTime =
                    subtitle.end_seconds ||
                    subtitle.end ||
                    subtitle.endSeconds ||
                    0;

                return `
                <div class="subtitle-item" data-start="${startTime}" data-end="${endTime}">
                    <span class="subtitle-time">${formatTime(startTime)} → ${formatTime(endTime)}</span>
                    <p class="subtitle-text">${subtitle.text || 'No text'}</p>
                </div>
            `}).join('');

            // Add click handlers for subtitle navigation
            document.querySelectorAll('.subtitle-item').forEach(item => {
                item.addEventListener('click', () => {
                    const time = parseFloat(item.dataset.start);
                    if (player && player.seekTo) {
                        player.seekTo(time);
                        player.playVideo();
                        scrollToVideo();
                    }
                });
            });
        } else {
            subtitlesContent.innerHTML = '<p class="text-gray-500">No subtitles available for this video.</p>';
        }
    }

    // Chart handling
    function createWordFrequencyChart(data) {
        // Check if data is null, undefined, or empty
        if (!data || Object.keys(data).length === 0) {
            console.warn('No word frequency data available');
            // Hide or clear the chart container
            const chartContainer = document.getElementById('wordFrequencyChart');
            if (chartContainer) {
                chartContainer.innerHTML = '<p class="text-gray-500">No word frequency data available.</p>';
            }
            return;
        }

        const ctx = document.getElementById('wordFrequencyChart').getContext('2d');
        const isDark = document.body.classList.contains('dark-theme');

        if (wordFrequencyChart) {
            wordFrequencyChart.destroy();
        }

        wordFrequencyChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: Object.keys(data).slice(0, 20),
                datasets: [{
                    label: 'Word Frequency',
                    data: Object.values(data).slice(0, 20),
                    backgroundColor: isDark ? '#60a5fa' : '#2563eb',
                    borderColor: isDark ? '#3b82f6' : '#1e40af',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: isDark ? '#334155' : '#e2e8f0'
                        },
                        ticks: {
                            color: isDark ? '#f1f5f9' : '#1e293b'
                        }
                    },
                    x: {
                        grid: {
                            color: isDark ? '#334155' : '#e2e8f0'
                        },
                        ticks: {
                            color: isDark ? '#f1f5f9' : '#1e293b'
                        }
                    }
                },
                plugins: {
                    legend: {
                        labels: {
                            color: isDark ? '#f1f5f9' : '#1e293b'
                        }
                    }
                }
            }
        });
    }

    function updateChartTheme(isDark) {
        if (wordFrequencyChart) {
            wordFrequencyChart.options.scales.y.grid.color = isDark ? '#334155' : '#e2e8f0';
            wordFrequencyChart.options.scales.x.grid.color = isDark ? '#334155' : '#e2e8f0';
            wordFrequencyChart.options.scales.y.ticks.color = isDark ? '#f1f5f9' : '#1e293b';
            wordFrequencyChart.options.scales.x.ticks.color = isDark ? '#f1f5f9' : '#1e293b';
            wordFrequencyChart.options.plugins.legend.labels.color = isDark ? '#f1f5f9' : '#1e293b';
            wordFrequencyChart.update();
        }
    }

    // Transcript search handling
    const searchTranscript = document.getElementById('searchTranscript');
    searchTranscript.addEventListener('input', (e) => {
        const searchText = e.target.value.toLowerCase();
        const transcriptContent = document.getElementById('transcriptContent');
        const text = transcriptContent.textContent;

        if (searchText) {
            const regex = new RegExp(searchText, 'gi');
            transcriptContent.innerHTML = transcriptContent.innerText.replace(regex, match =>
                `<span class="highlight">${match}</span>`
            );

        } else {
            transcriptContent.innerHTML = text;
        }
    });

    // Copy transcript functionality
    document.getElementById('copyTranscript').addEventListener('click', () => {
        const transcriptText = document.getElementById('transcriptContent').textContent;
        navigator.clipboard.writeText(transcriptText).then(() => {
            const notification = document.getElementById('copyNotification');
            notification.classList.add('show');
            setTimeout(() => {
                notification.classList.remove('show');
            }, 2000);
        });
    });

    // Export handling
    // Add export button handlers
    document.getElementById('exportPdf').addEventListener('click', () => handleExport('pdf'));
    document.getElementById('exportText').addEventListener('click', () => handleExport('txt'));

    async function handleExport(format) {
        const content = document.getElementById('summaryContent').textContent;
        const videoTitle = document.getElementById('videoTitle').textContent;
    
        try {
            const response = await fetch('/export-summary', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    content: content,
                    format: format,
                    title: videoTitle
                })
            });
    
            if (!response.ok) {
                throw new Error('Export failed');
            }
    
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `${videoTitle}_summary.${format}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (error) {
            console.error('Export error:', error);
            alert('Export failed');
        }
    }

    // SRT download handler
    document.getElementById('downloadSrt').addEventListener('click', () => {
        if (!currentVideoData?.srt_filename) {
            alert('No subtitles available for download');
            return;
        }
        const filename = currentVideoData.srt_filename;

        fetch(`/exports/${filename}`)
            .then(response => {
                if (!response.ok) throw new Error('SRT file not found');
                return response.blob();
            })
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
            })
            .catch(error => {
                console.error('Download error:', error);
                alert('Failed to download SRT file. Please try again.');
            });
    });

    // Tab switching
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

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            videoForm.dispatchEvent(new Event('submit'));
        }
        if (['1', '2', '3', '4'].includes(e.key) && !e.ctrlKey) {
            tabs[parseInt(e.key) - 1]?.click();
        }
        if (e.ctrlKey && e.key === 'f') {
            e.preventDefault();
            searchTranscript.focus();
        }

        const isSearchFocused = document.activeElement === searchTranscript;
        const isVideoFocused = document.activeElement === document.getElementById('videoUrl');
        // Only toggle theme if search transcript is not focused
        if (e.key === 't' && !e.ctrlKey && !isSearchFocused && !isVideoFocused) {
            themeToggle.click();
        }
    });

    // Form submission handler
    videoForm.addEventListener('submit', async function (event) {
        event.preventDefault();
        const videoUrl = document.getElementById('videoUrl').value;
        const summaryMode = document.getElementById('summaryMode').value;


        // Show loader
        loader.style.display = 'block';
        outputSection.style.display = 'none';

        try {
            const response = await fetch('/process', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ url: videoUrl, summary_mode: summaryMode })
            });

            // Add more detailed error checking
            if (!response.ok) {
                const errorText = await response.text();
                console.error('Server Error:', errorText);
                throw new Error(errorText || 'Failed to process video');
            }

            const data = await response.json();
            console.log("Full API Response:", data);  // Log full response

            // Add null checks before accessing properties
            if (!data || !data.metadata) {
                throw new Error('Invalid response from server');
            }

            // Update video player
            if (player) {
                player.destroy();
            }
            player = new YT.Player('player', {
                height: '390',
                width: '640',
                videoId: data.player_data.video_id,
                playerVars: {
                    'playsinline': 1
                }
            });

            // Clean up existing description elements before updating
            cleanupExistingDescription();

            currentVideoData = data;
            // Update metadata
            document.getElementById('videoTitle').textContent = data.metadata.title;
            document.getElementById('videoAuthor').textContent = data.metadata.author;
            document.getElementById('videoViews').textContent = `${data.metadata.views.toLocaleString()} views`;
            document.getElementById('videoDate').textContent = new Date(data.metadata.publish_date).toLocaleDateString();
            document.getElementById('videoDescription').textContent = data.metadata.description;
            initializeDescription(); // Initialize description expansion

            // Update content
            if (data.audio_filename) {
                const audioContainer = document.getElementById('audioPlayerContainer');
                initializeAudioPlayer(data.audio_filename);
            } else {
                document.getElementById('audioPlayerContainer').innerHTML = '';
            }

            function initializeAudioPlayer(audioFilename) {
                const audioContainer = document.getElementById('audioPlayerContainer');
                const audioHTML = `
                    <div class="custom-audio-player">
                        <audio id="customAudio" src="/exports/${audioFilename}"></audio>
                        <button class="play-pause-btn">
                            <i class="ri-play-fill"></i>
                        </button>
                        <div class="progress-container">
                            <div class="progress-bar"></div>
                        </div>
                        <span class="time-display">0:00</span>
                    </div>
                `;
            
                audioContainer.innerHTML = audioHTML;
            
                const audio = document.getElementById('customAudio');
                const playBtn = document.querySelector('.play-pause-btn');
                const progressBar = document.querySelector('.progress-bar');
                const progressContainer = document.querySelector('.progress-container');
                const timeDisplay = document.querySelector('.time-display');
            
                if (!audio || !playBtn || !progressBar || !progressContainer || !timeDisplay) {
                    console.error("Audio player elements not found.");
                    return;
                }
            
                audio.addEventListener('loadedmetadata', () => {
                    timeDisplay.textContent = formatTime(audio.duration);
                });
            
                audio.addEventListener('timeupdate', () => {
                    const progress = (audio.currentTime / audio.duration) * 100;
                    progressBar.style.width = `${progress}%`;
                    timeDisplay.textContent = formatTime(audio.currentTime);
                });
            
                playBtn.addEventListener('click', () => {
                    if (audio.paused) {
                        audio.play();
                        playBtn.innerHTML = '<i class="ri-pause-fill"></i>';
                    } else {
                        audio.pause();
                        playBtn.innerHTML = '<i class="ri-play-fill"></i>';
                    }
                });
            
                progressContainer.addEventListener('click', (e) => {
                    const rect = progressContainer.getBoundingClientRect();
                    const pos = (e.clientX - rect.left) / rect.width;
                    audio.currentTime = pos * audio.duration;
                });
            
                audio.addEventListener('ended', () => {
                    playBtn.innerHTML = '<i class="ri-play-fill"></i>';
                });
            }


            document.getElementById('summaryContent').innerHTML = formatSummary(data.summary);
            createWordFrequencyChart(data.word_frequency);

            // Update transcript and subtitles with new structure
            updateSubtitles({
                transcription: data.transcription,
                subtitles: data.subtitles,
                source: data.transcription_source
            });

            // Update recent videos
            updateRecentVideos({
                id: data.player_data.video_id,
                title: data.metadata.title,
                thumbnail: data.metadata.thumbnail
            });

            loader.style.display = 'none';
            outputSection.style.display = 'block';
            recentVideos.style.display = 'block';
        } catch (error) {
            console.error('Processing Error:', error);
            alert(`Error processing video: ${error.message}`);
            loader.style.display = 'none';
        }
    });

    function formatTime(seconds) {
        // Ensure seconds is a valid number
        const totalSeconds = Math.max(0, parseFloat(seconds) || 0);

        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const secs = Math.floor(totalSeconds % 60);

        // Format with hours if applicable
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }

        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }

    function formatSummary(summary) {
        if (!summary || summary.trim() === "") {
            return "<p class='text-gray-500'>No summary available.</p>";
        }
        const sections = summary.split(/\.\s+/).filter(s => s.trim());
        return sections.map(section =>
            `<div class="summary-section">
                <p>${section.trim()}.</p>
             </div>`
        ).join('');
    }


    function scrollToVideo() {
        const player = document.getElementById('player');
        player.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    // Shortcuts modal
    const shortcutsModal = document.getElementById('shortcutsModal');
    document.getElementById('showShortcuts').addEventListener('click', () => {
        shortcutsModal.style.display = 'block';
    });

    document.querySelector('.close-modal').addEventListener('click', () => {
        shortcutsModal.style.display = 'none';
    });

    // Initialize scroll buttons for recent videos
    document.addEventListener('DOMContentLoaded', () => {
        const scrollContainer = document.querySelector('.recent-videos-scroll');
        if (scrollContainer) {
            scrollContainer.addEventListener('scroll', updateScrollButtons);
            // Initial check
            updateScrollButtons();
            // Recheck on window resize
            window.addEventListener('resize', updateScrollButtons);
        }
    });
});