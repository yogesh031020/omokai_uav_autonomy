# Use an official lightweight Python image
FROM python:3.10-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies needed for MAVSDK and compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install python packages
RUN pip install --no-cache-dir \
    mavsdk \
    pytest

# Copy project source code into the container
COPY src/ /app/src/

# Set working directory to src for convenience
WORKDIR /app/src

# Set default command to run the CLI test (which runs in dry-run mode by default)
CMD ["python", "cli.py"]
