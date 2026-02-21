"""
Gunicorn configuration file for the ProfAI application.
"""

# The maximum time a worker can be silent before it's killed and restarted.
# This is crucial for long-running tasks like PDF processing and course generation.
timeout = 300  # 5 minutes (increased from the default of 30 seconds)

# The type of worker class to use for FastAPI
worker_class = "uvicorn.workers.UvicornWorker"

# The address and port to bind to
bind = "0.0.0.0:5001"

# Number of worker processes (a good starting point is 2 * num_cores + 1)
workers = 4

# Logging configuration
accesslog = "-"  # Log access to stdout
errorlog = "-"   # Log errors to stdout
loglevel = "info"
