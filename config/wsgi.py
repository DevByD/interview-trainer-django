"""WSGI config for Interview Trainer project."""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

# Alias for Vercel serverless WSGI runtime
app = application
