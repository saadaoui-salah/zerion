# Django Expert Brain

## CRITICAL RULES - NEVER BREAK THESE

1. **NEVER create files in `skills/` folder** - That's for Zerion-Core skill definitions only
2. **Django apps go in `apps/` folder** - Create apps like `apps/users/`, `apps/core/`
3. **Config folder matches project name** - `config/` or `project_name/`

## CORRECT Folder Structure

```
project_name/
├── manage.py
├── requirements.txt
├── config/                    # or project_name/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/                      # ALL Django apps go here
│   ├── __init__.py
│   ├── users/
│   │   ├── models.py
│   │   ├── views.py
│   │   └── ...
│   └── core/
│       ├── models.py
│       ├── views.py
│       └── ...
├── templates/
└── static/
```

## WRONG Structure (NEVER DO THIS)

```
WRONG: skills/                # This is for Zerion-Core skills
WRONG: skills/users/          # Never put Django apps here
WRONG: skills/models.py       # Never create Django files here
```

## Core Knowledge

### Django Project Setup Commands

```bash
# Create project
django-admin startproject config .

# Create apps directory (CORRECT location)
mkdir apps
touch apps/__init__.py

# Create Django app (CORRECT location)
cd apps
python manage.py startapp users
cd ..
```

### App Architecture
- Single responsibility principle
- Clear separation of concerns
- Reusable components
- Modular design

### Database Design
- Model relationships (ForeignKey, ManyToMany, OneToOne)
- Field types and options
- Query optimization
- Migration management

### Views and Templates
- Class-based views vs function-based views
- Template inheritance
- Static files management
- Form handling

### REST API Development
- Django REST Framework
- Serializers and viewsets
- Authentication and permissions
- API documentation

## Common Patterns

### Project Setup Pattern
```bash
python -m venv venv
source venv/bin/activate
pip install django
django-admin startproject config .
python manage.py startapp app_name
```

### Model Pattern
```python
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True

class Article(TimeStampedModel):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
```

### View Pattern
```python
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin

class ArticleListView(ListView):
    model = Article
    template_name = 'article_list.html'
    context_object_name = 'articles'
    paginate_by = 10

class ArticleDetailView(DetailView):
    model = Article
    template_name = 'article_detail.html'
```

### URL Pattern
```python
from django.urls import path
from . import views

app_name = 'articles'

urlpatterns = [
    path('', views.ArticleListView.as_view(), name='list'),
    path('<slug:slug>/', views.ArticleDetailView.as_view(), name='detail'),
]
```

### Template Pattern
```html
{% extends 'base.html' %}

{% block content %}
<h1>{{ object.title }}</h1>
<p>{{ object.content }}</p>
{% endblock %}
```

## Performance Optimization

### Database Queries
- Use `select_related()` for ForeignKey
- Use `prefetch_related()` for ManyToMany
- Use `only()` to limit fields
- Use `defer()` to defer fields
- Use `annotate()` for computed fields
- Use `aggregate()` for statistics

### Caching
- Use Django's caching framework
- Cache template fragments
- Cache query results
- Use Redis for distributed caching

### Static Files
- Use `collectstatic` for production
- Use `whitenoise` for serving
- Use CDN for static files
- Compress and minify assets

## Security Best Practices

### Authentication
- Use Django's built-in auth
- Use `LoginRequiredMixin` for protected views
- Use `@login_required` decorator
- Use `UserPassesTestMixin` for permissions

### Authorization
- Use Django's permission system
- Use object-level permissions
- Use role-based access control
- Audit user actions

### Data Protection
- Use environment variables
- Never commit secrets
- Use HTTPS
- Validate all input

## Testing Strategies

### Unit Tests
- Test models
- Test views
- Test forms
- Test commands

### Integration Tests
- Test API endpoints
- Test user flows
- Test database operations

### Performance Tests
- Load testing
- Stress testing
- Profiling queries

## Common Issues

### Migration Issues
```bash
# Reset migrations
python manage.py migrate app_name zero
python manage.py makemigrations
python manage.py migrate
```

### Static Files Issues
```bash
# Collect static files
python manage.py collectstatic

# Check static files
python manage.py findstatic filename
```

### Database Issues
```bash
# Reset database
rm db.sqlite3
python manage.py migrate
python manage.py createsuperuser
```

## Best Practices

1. Always use virtual environments
2. Freeze requirements regularly
3. Use environment variables for secrets
4. Write tests for all code
5. Use Django's built-in features
6. Follow Django conventions
7. Keep apps small and focused
8. Use version control
9. Document your code
10. Review code regularly
