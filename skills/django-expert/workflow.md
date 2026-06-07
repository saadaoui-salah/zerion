# Django Development Workflow

## Overview

This workflow guides you through creating a complete Django project from scratch, including virtual environment setup, app creation, models, views, templates, and deployment preparation.

## CRITICAL: Folder Structure Rules

1. **NEVER create files in `skills/` folder** - That's for Zerion-Core skills only
2. **Django apps go in `apps/` folder** - Always create apps there
3. **Config folder matches project name** - `config/` or `project_name/`

## Workflow Steps

### Step 1: Project Initialization

**Goal**: Set up the Django project structure with virtual environment and dependencies.

**Actions**:
1. Create project directory
2. Create and activate virtual environment
3. Install Django and dependencies
4. Create Django project
5. Create requirements.txt

**Commands**:
```bash
# Create project directory
mkdir project_name && cd project_name

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install django djangorestframework django-environ django-cors-headers

# Freeze requirements
pip freeze > requirements.txt

# Create Django project
django-admin startproject config .

# Create apps directory (IMPORTANT: not skills/, but apps/)
mkdir apps
touch apps/__init__.py
```

**Expected Files**:
- `venv/` - Virtual environment
- `requirements.txt` - Dependencies
- `manage.py` - Django management script
- `config/` - Project configuration
- `apps/` - Application directory (NEVER use skills/ for Django apps)

---

### Step 2: Settings Configuration

**Goal**: Configure Django settings for development and production.

**Actions**:
1. Create settings package
2. Configure base settings
3. Set up environment variables
4. Configure installed apps
5. Set up database

**Files to Create/Modify**:
- `config/settings/__init__.py`
- `config/settings/base.py`
- `config/settings/development.py`
- `config/settings/production.py`

**Key Settings**:
```python
# Installed apps should include:
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'rest_framework',
    'corsheaders',
    # Local apps (IMPORTANT: apps are in apps/ folder, NOT skills/)
    'apps.users',
    'apps.core',
]
```

**NOTE**: The `apps.` prefix is required because apps are in the `apps/` directory.

---

### Step 3: Users App Creation

**Goal**: Create a custom users app with user model.

**Actions**:
1. Create users app
2. Define CustomUser model
3. Configure admin
4. Create forms
5. Create views
6. Set up URLs

**Commands**:
```bash
cd apps
python manage.py startapp users
```

**Files to Create**:
- `apps/users/__init__.py`
- `apps/users/models.py`
- `apps/users/admin.py`
- `apps/users/forms.py`
- `apps/users/views.py`
- `apps/users/urls.py`
- `apps/users/tests.py`
- `apps/users/migrations/__init__.py`

---

### Step 4: Core App Creation

**Goal**: Create the main application with models, views, and templates.

**Actions**:
1. Create core app
2. Define models
3. Create views
4. Set up URLs
5. Create templates

**Commands**:
```bash
cd apps
python manage.py startapp core
```

**Files to Create**:
- `apps/core/__init__.py`
- `apps/core/models.py`
- `apps/core/views.py`
- `apps/core/urls.py`
- `apps/core/admin.py`
- `apps/core/tests.py`
- `apps/core/migrations/__init__.py`

---

### Step 5: URL Configuration

**Goal**: Set up URL routing for the project.

**Actions**:
1. Configure project URLs
2. Configure app URLs
3. Set up API URLs (if using REST framework)

**Files to Modify/Create**:
- `config/urls.py`
- `apps/users/urls.py`
- `apps/core/urls.py`
- `apps/core/api_urls.py` (optional)

---

### Step 6: Templates

**Goal**: Create base templates and page templates.

**Actions**:
1. Create base template
2. Create includes directory
3. Create page templates
4. Set up static files

**Directory Structure**:
```
templates/
├── base.html
├── includes/
│   ├── header.html
│   ├── footer.html
│   └── messages.html
├── users/
│   ├── signup.html
│   └── profile.html
└── core/
    ├── article_list.html
    └── article_detail.html
```

---

### Step 7: Static Files

**Goal**: Set up static files directory structure.

**Actions**:
1. Create static directory
2. Set up CSS files
3. Set up JavaScript files
4. Configure static files in settings

**Directory Structure**:
```
static/
├── css/
│   └── style.css
├── js/
│   └── main.js
└── images/
    └── logo.png
```

---

### Step 8: Database Migrations

**Goal**: Create and apply database migrations.

**Commands**:
```bash
# Make migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Verify migrations
python manage.py showmigrations
```

---

### Step 9: Testing

**Goal**: Write and run tests.

**Actions**:
1. Write model tests
2. Write view tests
3. Write form tests
4. Run test suite

**Commands**:
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test apps.core

# Run with coverage
coverage run --source='.' manage.py test
coverage report
```

---

### Step 10: Development Server

**Goal**: Start the development server and verify everything works.

**Commands**:
```bash
# Run development server
python manage.py runserver

# Run on specific port
python manage.py runserver 8080

# Run with autoreload
python manage.py runserver --noreload
```

**Verification Checklist**:
- [ ] Admin panel accessible at `/admin/`
- [ ] Static files loading correctly
- [ ] Templates rendering properly
- [ ] Database migrations applied
- [ ] User authentication working
- [ ] CRUD operations functioning

---

## Quick Start Script

```bash
#!/bin/bash
# quick_start.sh

# Create project
mkdir myproject && cd myproject

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install django djangorestframework django-environ django-cors-headers
pip freeze > requirements.txt

# Create Django project
django-admin startproject config .

# Create apps
mkdir apps
touch apps/__init__.py
cd apps
python manage.py startapp users
python manage.py startapp core
cd ..

# Initialize git
git init
echo "venv/" >> .gitignore
echo "*.pyc" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "db.sqlite3" >> .gitignore
echo "staticfiles/" >> .gitignore
echo "media/" >> .gitignore

echo "Django project created successfully!"
```

## Common Issues and Solutions

### Issue: "No module named 'django'"
**Solution**: Activate virtual environment and install Django
```bash
source venv/bin/activate
pip install django
```

### Issue: "Migration already exists"
**Solution**: Fake the migration or delete and recreate
```bash
python manage.py migrate --fake app_name
# OR
python manage.py migrate app_name zero
python manage.py migrate app_name
```

### Issue: "Static files not found"
**Solution**: Collect static files
```bash
python manage.py collectstatic
```

### Issue: "Template not found"
**Solution**: Check TEMPLATES DIRS setting and template path
```python
# In settings.py
TEMPLATES = [
    {
        'DIRS': [BASE_DIR / 'templates'],
        ...
    },
]
```
