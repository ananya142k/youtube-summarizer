FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY backend/ ./backend
COPY frontend/ ./frontend

# Set working directory to backend
WORKDIR /app/backend

# Create downloads directory
RUN mkdir -p downloads

# Expose the port the app runs on
EXPOSE 5000

# Use gunicorn to serve the application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]