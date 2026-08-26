import os
from django.core.wsgi import get_wsgi_application

# Portal folder mein settings.py hai
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'portal.settings')

app = get_wsgi_application()