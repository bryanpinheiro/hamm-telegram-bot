FROM python:3.12-slim

WORKDIR /app

# Install dependencies first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# SQLite file will live here, mounted as a volume so data survives container restarts/redeploys
VOLUME ["/app/data"]

# Expose Prometheus metrics port
EXPOSE 8000
EXPOSE 8001

# Run the application
CMD ["python", "src/main.py"]