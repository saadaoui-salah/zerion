# Django Expert Memory

## Common Patterns and Solutions

### Project Setup
- Always use virtual environments for Django projects
- Freeze requirements with `pip freeze > requirements.txt`
- Use `django-environ` for environment variables
- Create separate settings for development and production

### App Architecture
- Use apps for separation of concerns
- Keep apps small and focused
- Use `apps.py` for app configuration
- Create `management/commands` for custom commands

### Models
- Always define `__str__` method
- Use `related_name` for reverse relationships
- Use abstract base classes for common fields
- Use `Meta.ordering` for default ordering

### Views
- Use class-based views when possible
- Use mixins for reusable functionality
- Use `LoginRequiredMixin` for protected views
- Use `get_absolute_url` for model URLs

### Templates
- Use template inheritance with `base.html`
- Use `{% include %}` for reusable components
- Use `{% static %}` for static files
- Use `{% url %}` for URL reversal

### Forms
- Use `ModelForm` for model-related forms
- Use `Clean` methods for validation
- Use `Widget` attributes for styling
- Use `initial` for default values

### Testing
- Use `TestCase` for database tests
- Use `Client` for view tests
- Use `setUp` for test data
- Use `assertContains` for response testing

## Common Issues and Solutions

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

### Import Issues
```python
# Use absolute imports
from apps.users.models import CustomUser
from apps.core.models import Article

# Avoid circular imports
# Use get_user_model() for User model
from django.contrib.auth import get_user_model
User = get_user_model()
```

## Performance Tips

1. Use `select_related()` for ForeignKey fields
2. Use `prefetch_related()` for ManyToMany fields
3. Use `only()` to limit fields
4. Use `defer()` to defer fields
5. Use `annotate()` for computed fields
6. Use `aggregate()` for statistics
7. Use `exists()` instead of `count() > 0`
8. Use `values()` for dictionaries
9. Use `values_list()` for tuples
10. Use `bulk_create()` for multiple inserts

## Security Best Practices

1. Never commit secrets to version control
2. Use environment variables for sensitive data
3. Use `DEBUG=False` in production
4. Use `ALLOWED_HOSTS` in production
5. Use HTTPS in production
6. Use `CSRF` protection
7. Use `XSS` protection
8. Use `Content-Type` protection
9. Use `Session` security
10. Use `Password` validation
