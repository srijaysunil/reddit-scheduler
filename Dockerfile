# Use lightweight Python
FROM python:3.11-slim

# Set work directory inside container
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all app code
COPY . .

# Run Flask app
CMD ["python", "app/app.py"]
