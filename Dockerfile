# Use an official Python runtime as the base image
FROM python:3.9

# Set the working directory in the container
WORKDIR /app

# Copy the Python requirements file
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Python and HTML files to the container
COPY . .

# Set the environment variables
ENV FLASK_APP=starterApp.py
ENV FLASK_ENV=production

# Expose a port if your application needs it
EXPOSE 5000

# Define the command to run your application
CMD [ "flask", "run", "--host=0.0.0.0" ]
