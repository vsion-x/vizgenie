# demo/load-generator/Dockerfile - CORRECTED
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir requests psutil

# Copy script
COPY main.py .

# Run load generator
CMD ["python", "main.py"]