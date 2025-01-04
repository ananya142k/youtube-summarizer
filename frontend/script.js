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

    // Theme handling
    const themeToggle = document.getElementById('themeToggle');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');

    function setTheme(isDark) {
        document.body.classList.toggle('dark-theme', isDark);
        document.body.classList.toggle('light-theme', !isDark);
        themeToggle.innerHTML = isDark ? '<i class="ri-moon-line"></i>' : '<i class="ri-sun-line"></i>';
        localStorage.setItem('theme', isDark ? 'dark' : 'light');

        // Update chart if it exists
        updateChartTheme(isDark);
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

    // Chart handling
    function createWordFrequencyChart(data) {
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
            transcriptContent.innerHTML = text.replace(regex, match =>
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
    // Export handling
    document.querySelectorAll('.dropdown-content a').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const format = e.target.dataset.format;
            const videoTitle = document.getElementById('videoTitle').textContent;
            const sanitizedTitle = videoTitle.replace(/[^\w\s-]/g, '').replace(/\s+/g, '_');
            const filename = `${sanitizedTitle}.${format}`;

            fetch(`/exports/${filename}`)
                .then(response => {
                    if (!response.ok) throw new Error('Export not found');
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
                    console.error('Export error:', error);
                    alert('Failed to download file. Please try again.');
                });
        });
    });

    // SRT download handler
    document.getElementById('downloadSrt').addEventListener('click', () => {
        const videoTitle = document.getElementById('videoTitle').textContent;
        const sanitizedTitle = videoTitle.replace(/[^\w\s-]/g, '').replace(/\s+/g, '_');
        const filename = `${sanitizedTitle}.srt`;

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
        // Remove Ctrl + C handler
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
        if (e.key === 't' && !e.ctrlKey) {
            themeToggle.click();
        }
    });

    // Shortcuts modal
    const shortcutsModal = document.getElementById('shortcutsModal');
    document.getElementById('showShortcuts').addEventListener('click', () => {
        shortcutsModal.style.display = 'block';
    });

    document.querySelector('.close-modal').addEventListener('click', () => {
        shortcutsModal.style.display = 'none';
    });

    // Form submission
    videoForm.addEventListener('submit', async function (event) {
        event.preventDefault();
        const videoUrl = document.getElementById('videoUrl').value;
    
        // Hide loader
        loader.style.display = 'block';
        outputSection.style.display = 'none';
        updateLoadingSteps(0);
    
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
    
            // Update metadata
            document.getElementById('videoTitle').textContent = data.metadata.title;
            document.getElementById('videoAuthor').textContent = data.metadata.author;
            document.getElementById('videoViews').textContent = `${data.metadata.views.toLocaleString()} views`;
            document.getElementById('videoDate').textContent = new Date(data.metadata.publish_date).toLocaleDateString();
            document.getElementById('videoDescription').textContent = data.metadata.description;
    
            // Update content
            document.getElementById('summaryContent').innerHTML = formatSummary(data.summary);
            document.getElementById('transcriptContent').textContent = data.transcription;
            createWordFrequencyChart(data.word_frequency);
            updateSubtitles(data.transcription);
    
            // Update recent videos
            updateRecentVideos({
                id: data.player_data.video_id,
                title: data.metadata.title,
                thumbnail: data.metadata.thumbnail
            });
    
            loader.style.display = 'none';
            outputSection.style.display = 'block';
            recentVideos.style.display = 'block'; // Show recent videos after results
        } catch (error) {
            alert(`Error processing video: ${error.message}`);
            loader.style.display = 'none';
        }
    });

    // Helper functions
    function updateLoadingSteps(step) {
        const steps = document.querySelectorAll('.processing-steps .step');
        steps.forEach((s, i) => {
            s.classList.toggle('active', i === step);
        });
    }

    function formatSummary(summary) {
        const sections = summary.split(/\.\s+/).filter(s => s.trim());
        return sections.map(section =>
            `<div class="summary-section">
                <p>${section.trim()}.</p>
             </div>`
        ).join('');
    }

    function updateSubtitles(transcript) {
        const subtitlesContent = document.getElementById('subtitlesContent');
        
        // Split transcript into sentences using natural breaks
        const sentences = transcript.match(/[^.!?]+[.!?]+/g) || [];
        let currentTime = 0;
        const averageWordsPerSecond = 2.5; // Typical speaking rate
        
        const timestamps = sentences.map(sentence => {
            const words = sentence.trim().split(/\s+/).length;
            const duration = words / averageWordsPerSecond;
            const timestamp = {
                time: formatTime(currentTime),
                text: sentence.trim(),
                start: currentTime
            };
            currentTime += duration;
            return timestamp;
        });
    
        subtitlesContent.innerHTML = timestamps.map(ts =>
            `<div class="subtitle-item" data-time="${ts.start}">
                <span class="subtitle-time">${ts.time}</span>
                <p class="subtitle-text">${ts.text}</p>
             </div>`
        ).join('');
    
        // Update click handlers for more accurate syncing
        document.querySelectorAll('.subtitle-item').forEach(item => {
            item.addEventListener('click', () => {
                const time = parseFloat(item.dataset.time);
                if (player && player.seekTo) {
                    player.seekTo(time);
                    player.playVideo();
                    scrollToVideo();
                }
            });
        });
    }

    function formatTime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    function scrollToVideo() {
        const player = document.getElementById('player');
        player.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
});

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