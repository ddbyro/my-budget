# First stage: build
FROM python:3.10.12-slim-buster as build

# Set the working directory
WORKDIR /app

# Add the current directory contents into the container at /app
ADD . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Second stage: runtime
FROM python:3.10.12-slim-buster

# Set the working directory
WORKDIR /app

# Copy only the dependencies installation from the 1st stage image
COPY --from=build /usr/local /usr/local

# Ensure data directory exists
RUN mkdir -p /app/data

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Use gunicorn to run your application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0", "my-budget:app"]