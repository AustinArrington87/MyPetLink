# Use official Python 3.11 image as base
FROM python:3.11-slim-bullseye

# Set the working directory inside the container
WORKDIR /app

RUN apt-get update --allow-insecure-repositories && \
    apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file
COPY requirements.txt .

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_PROGRESS_BAR=off

# Install dependencies
RUN pip3 config --user set global.progress_bar off
RUN pip3 install --no-cache-dir -r requirements.txt
RUN pip3 install --no-cache-dir spacy
RUN python -m spacy download en_core_web_sm

# Copy the rest of the application files
COPY . .

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_ENV=production

# Create the upload directory
RUN mkdir -p /app/uploads

# Expose port for Flask
EXPOSE 5000

# Run the application
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]