# Use full Python 3.11 image
FROM python:3.11

# Set working directory inside container
WORKDIR /app

# Install system dependencies required by pip packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    libjpeg-dev \
    zlib1g-dev \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install --no-cache-dir Flask==2.3.5 \
                                 praw==7.8.0 \
                                 APScheduler==3.10.1 \
                                 pytz==2025.7 \
                                 requests==2.31.0

# Copy app folder into container
COPY ./app ./app

# Expose Flask port
EXPOSE 5000

# Run the app
CMD ["python", "app/app.py"]
