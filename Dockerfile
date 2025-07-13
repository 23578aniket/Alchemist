# Dockerfile
# Use a slim Python base image for smaller image size
FROM python:3.10-slim-buster

# Set working directory inside the container
WORKDIR /app

# Install system dependencies required for moviepy (ffmpeg) and potentially other libraries
# libsm6 and libxext6 are common dependencies for video processing in Linux environments
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose ports if your application has a web interface (not strictly needed for this backend)
# EXPOSE 8000

# Define entrypoint and default command (overridden by docker-compose for specific services)
CMD ["python", "main.py"]
```yaml