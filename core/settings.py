"""
Django settings for core project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env variables
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Security Settings
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-a)adzu!&mgw0+8w=q%q2-)hmfel)=o$!3rm*are-co^k#%+%50')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = ['*']


# Application definition
INSTALLED_APPS = [
    'cloudinary',
    'cloudinary_storage',
    'unfold',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'import_export',
    'portal',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media Files & Storage Handling
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

if not DEBUG:
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': os.environ.get('CLOUD_NAME'),
        'API_KEY': os.environ.get('CLOUD_API_KEY'),
        'API_SECRET': os.environ.get('CLOUD_API_SECRET'),
    }
    STORAGES = {
        "default": {
            "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }


# Email Configuration (Gmail SMTP)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_SSL = True
EMAIL_USE_TLS = False
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "mayanksingh9889659765@gmail.com")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "apualbvhfuzrquzk")
EMAIL_TIMEOUT = 10

DEFAULT_FROM_EMAIL = f"Central Exam Portal <{EMAIL_HOST_USER}>"
ADMIN_NOTIFICATION_EMAIL = EMAIL_HOST_USER


# Razorpay Payment Gateway
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', 'rzp_test_placeholder_key')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', 'placeholder_secret')


# Django Unfold Theme Configuration
UNFOLD = {
    "SITE_TITLE": "Examination Authority Console",
    "SITE_HEADER": "Central Examination Authority",
    "SITE_URL": "/admin/",
    "SITE_ICON": {
        "light": lambda request: "",
        "dark": lambda request: "",
    },
    "DASHBOARD_CALLBACK": None,
    "THEME": "light",
    "COLORS": {
        "primary": {
            "50": "240 249 255",
            "100": "224 242 254",
            "200": "186 230 253",
            "300": "125 211 252",
            "400": "56 189 248",
            "500": "14 165 233",
            "600": "2 132 199",
            "700": "3 105 161",
            "800": "7 89 133",
            "900": "12 74 110",
            "950": "8 47 73",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
        "navigation": [
            {
                "title": "Operations & Applications",
                "separator": True,
                "items": [
                    {
                        "title": "Candidate Applications",
                        "icon": "people",
                        "link": "/admin/portal/candidate/",
                    },
                    {
                        "title": "📥 CSV / Excel Master Importer",
                        "icon": "upload_file",
                        "link": "/admin/portal/candidate/import-sheet/",
                    },
                    {
                        "title": "Result Evaluation Desk",
                        "icon": "verified",
                        "link": "/admin/portal/presentcandidateresult/",
                    },
                    {
                        "title": "Exam Centers & Shifts",
                        "icon": "apartment",
                        "link": "/admin/portal/examcenter/",
                    },
                ],
            },
            {
                "title": "System & Settings",
                "separator": True,
                "items": [
                    {
                        "title": "Staff & Admin Users",
                        "icon": "shield",
                        "link": "/admin/auth/user/",
                    },
                    {
                        "title": "Portal Global Settings",
                        "icon": "settings",
                        "link": "/admin/portal/portalsetting/",
                    },
                    {
                        "title": "Grievance Helpdesk",
                        "icon": "headset_mic",
                        "link": "/admin/portal/grievance/",
                    },
                ],
            },
        ],
    },
}