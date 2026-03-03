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

# upgrade pip and install runtime dependencies explicitly to avoid
# building the local project (flat layout contains multiple top-level
# packages which setuptools refuses to build automatically)
RUN pip install --upgrade pip \
	&& pip install --no-cache-dir \
	   "uvicorn[standard]" \
	   "fastapi==0.115.0" \
	   "python-multipart==0.0.22" \
	   "qreader>=3.16.0" \
	   "opencv-python-headless==4.9.0.80"

COPY app ./app

# Start the app with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
