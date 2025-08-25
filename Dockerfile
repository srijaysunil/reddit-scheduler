# Use full Python image
FROM python:3.11

# Set working directory inside container
WORKDIR /app

# Copy requirements from repo root and install dependencies
COPY requirements.txt .
#RUN pip install --no-cache-dir -r requirements.txt
RUN pip install Flask==2.3.5 praw==7.8.0 APScheduler==3.10.1 pytz==2025.7 requests==2.31.0


# Copy the app folder
COPY ./app ./app

# Expose Flask port
EXPOSE 5000

# Run the app
CMD ["python", "app/app.py"]
