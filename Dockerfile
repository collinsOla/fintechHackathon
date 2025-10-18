# Use official Python image
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /fintechHackathon

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Django project folder into container
COPY hackathon/ ./hackathon

# Set working directory to Django project inside container
WORKDIR /fintechHackathon/hackathon

# Expose port
EXPOSE 8000

# Run Django development server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
