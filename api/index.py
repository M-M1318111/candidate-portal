import os
from django.core.wsgi import get_wsgi_application

# Replace 'portal' with the folder name containing your settings.py
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portal.settings')

app = get_wsgi_application()