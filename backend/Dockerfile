# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend source
COPY . .

# Adjust this to whatever actually starts your backend
CMD ["python", "main.py"]
