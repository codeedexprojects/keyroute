"""
Django settings for keyroute project.

Generated by 'django-admin startproject' using Django 5.1.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.1/ref/settings/
"""

import firebase_admin
from firebase_admin import credentials
import os

# Firebase initialization
if not firebase_admin._apps:
    try:
        # Replace with your actual path to the Firebase service account key
        FIREBASE_KEY_PATH = os.path.join(BASE_DIR, 'keyrouteuser-firebase-adminsdk-fbsvc-2b142f3163.json')
        
        if os.path.exists(FIREBASE_KEY_PATH):
            cred = credentials.Certificate(FIREBASE_KEY_PATH)
            firebase_admin.initialize_app(cred)
            print("Firebase initialized successfully")
        else:
            print(f"Firebase key file not found at: {FIREBASE_KEY_PATH}")
    except Exception as e:
        print(f"Firebase initialization error: {e}")


from pathlib import Path
from datetime import timedelta


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

import os
from dotenv import load_dotenv

import pymysql
pymysql.install_as_MySQLdb()


# Load environment variables from .env file
load_dotenv()

GOOGLE_MAPS_API_KEY = "AIzaSyCnNixdBmNb0cOCet3HofxffjMSKOsAm4w"
RAZORPAY_KEY_ID = 'rzp_live_xAgEAw1FD7Xhp6'
RAZORPAY_KEY_SECRET = 'MeJwJ804gRHeBWEZozuEYWbg'


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-z-9l67w3%e0myi15k%dpjv5c61z3-*)&7$f6mtflm7*+$g$1+&'

GOOGLE_DISTANCE_MATRIX_API_KEY = 'AIzaSyCnNixdBmNb0cOCet3HofxffjMSKOsAm4w'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'rest_framework',
    'corsheaders',
    'users.apps.UsersConfig',
    'vendors',
    'bookings',
    'payments',
    'admin_panel',
    'notifications',
    'reviews',
]

EMAIL_BACKEND =  "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587 
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "keyroutebus@gmail.com"
EMAIL_HOST_PASSWORD = "glfe sqzv rlcc yyiz"

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

ROOT_URLCONF = 'keyroute.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'keyroute.wsgi.application'



SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=150),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=150),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'ALGORITHM': 'HS256',
}
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True







# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }








# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases


# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'NAME': 'keyroute$database',
#         'USER': 'keyroute',
#         'PASSWORD': 'admin@123',
#         'HOST': 'keyroute.mysql.pythonanywhere-services.com',
#         'PORT': '3306',
#         'OPTIONS': {
#             'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
#         }
#     }
# }



DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'keyroute_db',  
        'USER': 'keyroute',
        'PASSWORD': 'admin123',
        'HOST': 'keyroute-db.cp86aus24g28.ap-south-1.rds.amazonaws.com',
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"
        },
    }
}

# }
# DATABASES['default']['CONN_MAX_AGE'] = 600  # Keep connections alive for 10 minutes
# DATABASES['default']['OPTIONS'] = {
#     'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
#     'connect_timeout': 20,  # Increase timeout
#     'charset': 'utf8mb4',  # Use efficient encoding
# }


AUTH_USER_MODEL = 'admin_panel.User'

# settings.py
FILE_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024 #30mb



# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = 'static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


import firebase_admin
from firebase_admin import credentials
import os

# Define BASE_DIR if not already defined
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if not firebase_admin._apps:
    try:
        FIREBASE_KEY_PATH = os.path.join(BASE_DIR, 'firbase', 'keyroutproject-firebase-adminsdk-fbsvc-ea737454d9.json')
        
        if os.path.exists(FIREBASE_KEY_PATH):
            cred = credentials.Certificate(FIREBASE_KEY_PATH)
            firebase_admin.initialize_app(cred)
            print("Firebase initialized successfully")
        else:
            print(f"Firebase key file not found at: {FIREBASE_KEY_PATH}")
    except Exception as e:
        print(f"Error initializing Firebase: {e}")





FIREBASE_PROJECT_ID = "BD3AfQV-3O8zHTDbdPPZUT59SVSvhdbjEBERKUnKyBp4RrZs166DO6ROUqcJKueji6WQ5nwxvJQfy4peqND7Fog"
FIREBASE_SERVER_KEY = 'BD3AfQV-3O8zHTDbdPPZUT59SVSvhdbjEBERKUnKyBp4RrZs166DO6ROUqcJKueji6WQ5nwxvJQfy4peqND7Fog'
RAZORPAY_KEY_ID = 'rzp_live_xAgEAw1FD7Xhp6'
RAZORPAY_KEY_SECRET = 'MeJwJ804gRHeBWEZozuEYWbg'
