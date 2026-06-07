# Django Development Examples

## CRITICAL RULES - READ THIS FIRST

1. **NEVER create files in `skills/` folder** - That's for Zerion-Core skill definitions
2. **Django apps go in `apps/` folder** - Create apps like `apps/users/`, `apps/core/`
3. **Config folder matches project name** - `config/` or `project_name/`

## Complete Project Setup

### Example 1: Create a Blog Project

```bash
# Step 1: Create project directory
mkdir blog_project && cd blog_project

# Step 2: Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Step 3: Install dependencies
pip install django djangorestframework django-environ django-cors-headers Pillow
pip freeze > requirements.txt

# Step 4: Create Django project
django-admin startproject config .

# Step 5: Create apps directory (IMPORTANT: NOT skills/, but apps/)
mkdir apps
touch apps/__init__.py
cd apps
python manage.py startapp users
python manage.py startapp blog
cd ..

# Step 6: Create directory structure
mkdir templates
mkdir templates/includes
mkdir templates/users
mkdir templates/blog
mkdir static
mkdir static/css
mkdir static/js
mkdir static/images
mkdir media
```

**WRONG structure (DO NOT DO THIS):**
```
WRONG: skills/           # This is for Zerion-Core skills
WRONG: skills/users/     # Never put Django apps here
```

**CORRECT structure:**
```
CORRECT: apps/           # Django apps directory
CORRECT: apps/users/     # Django app inside apps/
CORRECT: apps/blog/      # Another Django app inside apps/
```

### Example 2: Settings Configuration

```python
# config/settings/base.py
import os
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-this-in-production')

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
    'apps.users.apps.UsersConfig',
    'apps.blog.apps.BlogConfig',
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

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_USER_MODEL = 'users.CustomUser'

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
}
```

## App Creation Examples

### Example 3: Users App

```python
# apps/users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    website = models.URLField(blank=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'
    
    def __str__(self):
        return self.email
    
    def get_avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return '/static/images/default-avatar.png'
```

```python
# apps/users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['email', 'username', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['is_active', 'is_staff', 'is_superuser']
    search_fields = ['email', 'username']
    ordering = ['email']
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('username', 'avatar', 'bio', 'website')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2'),
        }),
    )
```

```python
# apps/users/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    
    class Meta:
        model = CustomUser
        fields = ('email', 'username', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ('email', 'username', 'avatar', 'bio', 'website')
```

```python
# apps/users/views.py
from django.shortcuts import render, redirect
from django.views.generic import CreateView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import login
from django.urls import reverse_lazy
from .models import CustomUser
from .forms import CustomUserCreationForm

class SignUpView(CreateView):
    model = CustomUser
    form_class = CustomUserCreationForm
    template_name = 'users/signup.html'
    success_url = reverse_lazy('login')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response

class ProfileView(LoginRequiredMixin, DetailView):
    model = CustomUser
    template_name = 'users/profile.html'
    context_object_name = 'user_profile'
    
    def get_object(self, queryset=None):
        return self.request.user

class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    fields = ['avatar', 'bio', 'website']
    template_name = 'users/profile_edit.html'
    success_url = reverse_lazy('users:profile')
    
    def get_object(self, queryset=None):
        return self.request.user
```

### Example 4: Blog App

```python
# apps/blog/models.py
from django.db import models
from django.conf import settings
from django.utils.text import slugify

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Tag(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Post(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
    )
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    excerpt = models.TextField(max_length=300, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='posts'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posts'
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name='posts')
    featured_image = models.ImageField(upload_to='posts/', blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    def get_excerpt(self):
        if self.excerpt:
            return self.excerpt
        return self.content[:200] + '...' if len(self.content) > 200 else self.content
```

```python
# apps/blog/views.py
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from .models import Post, Category, Tag

class PostListView(ListView):
    model = Post
    template_name = 'blog/post_list.html'
    context_object_name = 'posts'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = Post.objects.filter(status='published')
        
        # Search
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(content__icontains=query)
            )
        
        # Filter by category
        category_slug = self.request.GET.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        
        # Filter by tag
        tag_slug = self.request.GET.get('tag')
        if tag_slug:
            queryset = queryset.filter(tags__slug=tag_slug)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['tags'] = Tag.objects.all()
        return context

class PostDetailView(DetailView):
    model = Post
    template_name = 'blog/post_detail.html'
    context_object_name = 'post'
    
    def get_queryset(self):
        if self.request.user.is_staff:
            return Post.objects.all()
        return Post.objects.filter(status='published')

class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    template_name = 'blog/post_form.html'
    fields = ['title', 'content', 'excerpt', 'category', 'tags', 'featured_image', 'status']
    
    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

class PostUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    template_name = 'blog/post_form.html'
    fields = ['title', 'content', 'excerpt', 'category', 'tags', 'featured_image', 'status']
    
    def get_queryset(self):
        return Post.objects.filter(author=self.request.user)
```

## REST API Examples

### Example 5: API Serializers

```python
# apps/blog/serializers.py
from rest_framework import serializers
from .models import Post, Category, Tag
from apps.users.serializers import UserSerializer

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug']

class CategorySerializer(serializers.ModelSerializer):
    post_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'post_count']
    
    def get_post_count(self, obj):
        return obj.posts.filter(status='published').count()

class PostListSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    
    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'excerpt', 'author', 'category',
            'tags', 'featured_image', 'status', 'created_at', 'published_at'
        ]

class PostDetailSerializer(PostListSerializer):
    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + ['content', 'updated_at']

class PostCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ['title', 'content', 'excerpt', 'category', 'tags', 'featured_image', 'status']
    
    def create(self, validated_data):
        tags = validated_data.pop('tags', [])
        post = Post.objects.create(**validated_data)
        post.tags.set(tags)
        return post
```

### Example 6: API Views

```python
# apps/blog/api_views.py
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Post, Category, Tag
from .serializers import (
    PostListSerializer, PostDetailSerializer, PostCreateSerializer,
    CategorySerializer, TagSerializer
)

class IsAuthorOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.author == request.user

class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'category__slug', 'tags__slug']
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'published_at']
    lookup_field = 'slug'
    
    def get_serializer_class(self):
        if self.action == 'list':
            return PostListSerializer
        elif self.action == 'create':
            return PostCreateSerializer
        return PostDetailSerializer
    
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_posts(self, request):
        posts = Post.objects.filter(author=request.user)
        serializer = PostListSerializer(posts, many=True)
        return Response(serializer.data)

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'

class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'
```

## Template Examples

### Example 7: Base Template

```html
<!-- templates/base.html -->
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}My Django Blog{% endblock %}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="{% static 'css/style.css' %}">
    {% block extra_css %}{% endblock %}
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="{% url 'blog:post_list' %}">My Blog</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="{% url 'blog:post_list' %}">Home</a>
                    </li>
                </ul>
                <ul class="navbar-nav">
                    {% if user.is_authenticated %}
                        <li class="nav-item">
                            <a class="nav-link" href="{% url 'blog:post_create' %}">New Post</a>
                        </li>
                        <li class="nav-item dropdown">
                            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                                {{ user.username }}
                            </a>
                            <ul class="dropdown-menu dropdown-menu-end">
                                <li><a class="dropdown-item" href="{% url 'users:profile' %}">Profile</a></li>
                                <li><hr class="dropdown-divider"></li>
                                <li><a class="dropdown-item" href="{% url 'logout' %}">Logout</a></li>
                            </ul>
                        </li>
                    {% else %}
                        <li class="nav-item">
                            <a class="nav-link" href="{% url 'login' %}">Login</a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="{% url 'users:signup' %}">Sign Up</a>
                        </li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>

    <main class="container my-4">
        {% if messages %}
            {% for message in messages %}
                <div class="alert alert-{{ message.tags }} alert-dismissible fade show">
                    {{ message }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            {% endfor %}
        {% endif %}

        {% block content %}{% endblock %}
    </main>

    <footer class="bg-dark text-white py-4 mt-5">
        <div class="container text-center">
            <p>&copy; 2024 My Django Blog. All rights reserved.</p>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{% static 'js/main.js' %}"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### Example 8: Post List Template

```html
<!-- templates/blog/post_list.html -->
{% extends 'base.html' %}

{% block title %}Blog Posts - My Django Blog{% endblock %}

{% block content %}
<div class="row">
    <div class="col-md-8">
        <h1 class="mb-4">Blog Posts</h1>
        
        {% if posts %}
            {% for post in posts %}
                <article class="card mb-4">
                    {% if post.featured_image %}
                        <img src="{{ post.featured_image.url }}" class="card-img-top" alt="{{ post.title }}">
                    {% endif %}
                    <div class="card-body">
                        <h2 class="card-title">
                            <a href="{% url 'blog:post_detail' post.slug %}">{{ post.title }}</a>
                        </h2>
                        <p class="text-muted">
                            By {{ post.author.username }} | 
                            {{ post.created_at|date:"F j, Y" }}
                            {% if post.category %}
                                | {{ post.category.name }}
                            {% endif %}
                        </p>
                        <p class="card-text">{{ post.get_excerpt }}</p>
                        <a href="{% url 'blog:post_detail' post.slug %}" class="btn btn-primary">Read More</a>
                    </div>
                </article>
            {% endfor %}
            
            {% if is_paginated %}
                <nav aria-label="Page navigation">
                    <ul class="pagination justify-content-center">
                        {% if page_obj.has_previous %}
                            <li class="page-item">
                                <a class="page-link" href="?page={{ page_obj.previous_page_number }}">Previous</a>
                            </li>
                        {% endif %}
                        
                        {% for num in page_obj.paginator.page_range %}
                            {% if page_obj.number == num %}
                                <li class="page-item active"><span class="page-link">{{ num }}</span></li>
                            {% else %}
                                <li class="page-item"><a class="page-link" href="?page={{ num }}">{{ num }}</a></li>
                            {% endif %}
                        {% endfor %}
                        
                        {% if page_obj.has_next %}
                            <li class="page-item">
                                <a class="page-link" href="?page={{ page_obj.next_page_number }}">Next</a>
                            </li>
                        {% endif %}
                    </ul>
                </nav>
            {% endif %}
        {% else %}
            <div class="alert alert-info">No posts found.</div>
        {% endif %}
    </div>
    
    <div class="col-md-4">
        <div class="card mb-4">
            <div class="card-header">Search</div>
            <div class="card-body">
                <form method="get" action="{% url 'blog:post_list' %}">
                    <div class="input-group">
                        <input type="text" class="form-control" name="q" placeholder="Search posts..." value="{{ request.GET.q }}">
                        <button class="btn btn-outline-secondary" type="submit">Search</button>
                    </div>
                </form>
            </div>
        </div>
        
        <div class="card mb-4">
            <div class="card-header">Categories</div>
            <ul class="list-group list-group-flush">
                {% for category in categories %}
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        <a href="?category={{ category.slug }}">{{ category.name }}</a>
                        <span class="badge bg-primary rounded-pill">{{ category.post_count }}</span>
                    </li>
                {% endfor %}
            </ul>
        </div>
        
        <div class="card">
            <div class="card-header">Tags</div>
            <div class="card-body">
                {% for tag in tags %}
                    <a href="?tag={{ tag.slug }}" class="badge bg-secondary text-decoration-none me-1">{{ tag.name }}</a>
                {% endfor %}
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

## Testing Examples

### Example 9: Model Tests

```python
# apps/blog/tests.py
from django.test import TestCase
from django.utils.text import slugify
from apps.users.models import CustomUser
from .models import Post, Category, Tag

class CategoryModelTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name='Technology',
            description='Tech articles'
        )
    
    def test_category_creation(self):
        self.assertEqual(self.category.name, 'Technology')
        self.assertEqual(self.category.slug, slugify('Technology'))
    
    def test_category_str(self):
        self.assertEqual(str(self.category), 'Technology')

class PostModelTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.category = Category.objects.create(name='Tech')
        self.tag = Tag.objects.create(name='Django')
        self.post = Post.objects.create(
            title='Test Post',
            content='Test content',
            author=self.user,
            category=self.category,
            status='published'
        )
        self.post.tags.add(self.tag)
    
    def test_post_creation(self):
        self.assertEqual(self.post.title, 'Test Post')
        self.assertEqual(self.post.author, self.user)
        self.assertEqual(self.post.category, self.category)
    
    def test_post_slug(self):
        self.assertEqual(self.post.slug, slugify('Test Post'))
    
    def test_post_str(self):
        self.assertEqual(str(self.post), 'Test Post')
    
    def test_post_tags(self):
        self.assertIn(self.tag, self.post.tags.all())
    
    def test_post_excerpt(self):
        self.assertEqual(self.post.get_excerpt(), self.post.content)
```

### Example 10: View Tests

```python
from django.test import TestCase, Client
from django.urls import reverse
from .models import Post, Category
from apps.users.models import CustomUser

class PostListViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.category = Category.objects.create(name='Tech')
        self.post = Post.objects.create(
            title='Test Post',
            content='Test content',
            author=self.user,
            category=self.category,
            status='published'
        )
    
    def test_post_list_view(self):
        response = self.client.get(reverse('blog:post_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Post')
    
    def test_post_list_search(self):
        response = self.client.get(reverse('blog:post_list') + '?q=Test')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Post')

class PostDetailViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.post = Post.objects.create(
            title='Test Post',
            content='Test content',
            author=self.user,
            status='published'
        )
    
    def test_post_detail_view(self):
        response = self.client.get(
            reverse('blog:post_detail', kwargs={'slug': self.post.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Post')
```

## Management Commands

### Example 11: Seed Data Command

```python
# apps/blog/management/commands/seed_blog.py
from django.core.management.base import BaseCommand
from apps.users.models import CustomUser
from apps.blog.models import Category, Tag, Post

class Command(BaseCommand):
    help = 'Seed database with sample blog data'
    
    def add_arguments(self, parser):
        parser.add_argument('--posts', type=int, default=10, help='Number of posts to create')
    
    def handle(self, *args, **options):
        posts_count = options['posts']
        
        # Create admin user
        admin, _ = CustomUser.objects.get_or_create(
            email='admin@example.com',
            defaults={
                'username': 'admin',
                'is_staff': True,
                'is_superuser': True
            }
        )
        admin.set_password('admin123')
        admin.save()
        
        # Create categories
        categories = []
        for name in ['Technology', 'Programming', 'Design', 'Business']:
            cat, _ = Category.objects.get_or_create(name=name)
            categories.append(cat)
        
        # Create tags
        tags = []
        for name in ['Django', 'Python', 'JavaScript', 'CSS', 'HTML']:
            tag, _ = Tag.objects.get_or_create(name=name)
            tags.append(tag)
        
        # Create posts
        for i in range(posts_count):
            post = Post.objects.create(
                title=f'Blog Post {i+1}',
                content=f'This is the content for blog post {i+1}. ' * 10,
                author=admin,
                category=categories[i % len(categories)],
                status='published'
            )
            post.tags.add(*tags[:2])
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {posts_count} blog posts')
        )
```

## Deployment Checklist

### Example 12: Production Settings

```python
# config/settings/production.py
from .base import *
import dj_database_url

DEBUG = False

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost').split(',')

# Database
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL', default='sqlite:///db.sqlite3')
    )
}

# Security
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Static files
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': True,
        },
    },
}
```
