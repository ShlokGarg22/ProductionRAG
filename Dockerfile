FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (if any are needed for Python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Fix the missing libpq and redis libraries without busting the cache
RUN pip install "psycopg[binary]" redis redisvl

# Expose the port Uvicorn will run on
EXPOSE 8000

# Run the FastAPI app using Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
