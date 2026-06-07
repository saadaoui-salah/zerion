# Django Project Setup Guide

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Git (optional, for version control)

## Virtual Environment Setup

### Why Use Virtual Environments?

Virtual environments isolate your project's dependencies from the system Python and other projects. This prevents version conflicts and makes dependency management easier.

### Creating a Virtual Environment

#### Windows

```bash
# Navigate to your project directory
cd C:\Users\YourName\Projects\myproject

# Create virtual environment
python -m venv venv

# Activate the virtual environment
venv\Scripts\activate

# Verify activation (should show venv path)
where python
```

#### Linux/Mac

```bash
# Navigate to your project directory
cd ~/Projects/myproject

# Create virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Verify activation (should show venv path)
which python
```

### Deactivating the Virtual Environment

```bash
deactivate
```

## Installing Django and Dependencies

### Basic Installation

```bash
# Make sure virtual environment is activated
pip install django

# Verify installation
python -m django --version
```

### Installing Common Dependencies

```bash
# Core Django packages
pip install django djangorestframework django-environ

# Database (if using PostgreSQL)
pip install psycopg2-binary

# Static files
pip install whitenoise

# Image handling
pip install Pillow

# CORS support
pip install django-cors-headers

# Environment variables
pip install python-decouple

# Freeze all dependencies
pip freeze > requirements.txt
```

### Installing from Requirements File

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install all dependencies
pip install -r requirements.txt
```

## Creating a Django Project

### Method 1: django-admin

```bash
# Create project in current directory
django-admin startproject config .

# This creates:
# manage.py
# config/
#   __init__.py
#   settings.py
#   urls.py
#   asgi.py
#   wsgi.py
```

### Method 2: python manage.py

```bash
# Create project
python manage.py startproject config .
```

### Project Structure

```
myproject/
├── manage.py
├── requirements.txt
├── .env
├── .gitignore
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── apps/
│   └── __init__.py
├── templates/
├── static/
│   ├── css/
│   ├── js/
│   └── images/
└── media/
```

## Creating Django Apps

### Creating an App

```bash
# Create apps directory
mkdir apps
touch apps/__init__.py

# Navigate to apps directory
cd apps

# Create app
python manage.py startapp users

# Go back to project root
cd ..
```

### App Structure

```
apps/users/
├── __init__.py
├── admin.py
├── apps.py
├── models.py
├── tests.py
├── views.py
├── migrations/
│   └── __init__.py
└── management/
    └── commands/
        └── __init__.py
```

## Settings Configuration

### Basic Settings

```python
# config/settings.py
import os
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='your-secret-key-here')

DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party apps
    'rest_framework',
    'corsheaders',
    # Local apps
    'apps.users',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_USER_MODEL = 'users.CustomUser'

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
```

### Environment Variables (.env)

```bash
# .env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
```

## Database Setup

### Creating Models

```python
# apps/users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
```

### Running Migrations

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

## Static Files

### Directory Structure

```
static/
├── css/
│   └── style.css
├── js/
│   └── main.js
└── images/
    └── logo.png
```

### Collecting Static Files

```bash
# Collect all static files to STATIC_ROOT
python manage.py collectstatic
```

## Running the Development Server

```bash
# Start development server
python manage.py runserver

# Start on specific port
python manage.py runserver 8080

# Start with autoreload disabled
python manage.py runserver --noreload
```

## Common Commands Reference

```bash
# Project management
django-admin startproject project_name .
python manage.py startapp app_name
python manage.py createsuperuser
python manage.py changepassword username

# Database
python manage.py makemigrations
python manage.py migrate
python manage.py dbshell
python manage.py showmigrations

# Static files
python manage.py collectstatic
python manage.py findstatic filename

# Testing
python manage.py test
python manage.py test apps.app_name
python manage.py test apps.app_name.tests.TestCaseClass

# Shell
python manage.py shell
python manage.py shell_plus  # if django-extensions installed

# Development
python manage.py runserver
python manage.py check
python manage.py diffsettings
```

## Troubleshooting

### Common Issues

1. **"No module named 'django'"**
   - Solution: Activate virtual environment and install Django

2. **"Migration already exists"**
   - Solution: `python manage.py migrate --fake app_name`

3. **"Static files not found"**
   - Solution: Run `python manage.py collectstatic`

4. **"Template not found"**
   - Solution: Check TEMPLATES DIRS setting

5. **"Port already in use"**
   - Solution: Use `python manage.py runserver 8080` for different port
