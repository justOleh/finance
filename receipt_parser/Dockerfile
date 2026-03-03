FROM python:3.11-slim
WORKDIR /app

# Install system dependencies required by qreader and opencv
RUN apt-get update && apt-get install -y --no-install-recommends \
	libxcb1 \
	libxkbcommon0 \
	libxkbcommon-x11-0 \
	libdbus-1-3 \
	libfontconfig1 \
	libfreetype6 \
	libx11-6 \
	libxext6 \
	libxrender1 \
	libgl1 \
	libglib2.0-0 \
	libzbar0 \
	&& apt-get clean && rm -rf /var/lib/apt/lists/*

# copy pyproject first so dependencies can be installed before copying source
COPY pyproject.toml ./

RUN pip install --upgrade pip \
	&& pip install --no-cache-dir .

COPY app ./app

# Start the app with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
