FROM python:3.11

WORKDIR /app

# Install OS libraries needed for pip packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages directly
RUN pip install Flask==2.3.5 \
                praw==7.8.0 \
                APScheduler==3.10.1 \
                pytz==2025.7 \
                requests==2.31.0

# Copy app code
COPY ./app ./app

EXPOSE 5000

CMD ["python", "app/app.py"]
