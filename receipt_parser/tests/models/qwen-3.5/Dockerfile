# Dockerfile for Qwen receipt parser using local pip environment
FROM python:3.10-slim

# Set workdir
WORKDIR /app

# Copy requirements from local venv
COPY . .

# If you have a requirements.txt, use it. Otherwise, export from venv:
# pip freeze > requirements.txt
COPY requirements.txt ./

# Install system dependencies (for opencv, pillow, etc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        python3-opencv \
        libgl1-mesa-glx \
        libglib2.0-0 \
        && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port if needed (e.g., for API)
EXPOSE 8000

# Set entrypoint (adjust as needed)
CMD ["python", "main.py"]
