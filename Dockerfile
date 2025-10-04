# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies and gunicorn
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy the entire application
COPY . .

# Set environment variables
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# Expose the port
EXPOSE 5000

# Use Gunicorn WSGI server instead of Flask dev server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--chdir", "web_ui", "app:app"]