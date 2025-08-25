# Full Python image
FROM python:3.11

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY ./app ./app

EXPOSE 5000

# Run the Flask app
CMD ["python", "app/app.py"]
