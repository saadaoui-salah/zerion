# Django Models Guide

## Overview

Django models define the structure of your database. They are Python classes that represent database tables.

## Basic Model Structure

```python
from django.db import models

class Article(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'article'
        verbose_name_plural = 'articles'
    
    def __str__(self):
        return self.title
```

## Field Types

### Text Fields

```python
# Short text (up to 255 characters)
name = models.CharField(max_length=100)

# Long text
content = models.TextField()

# Email
email = models.EmailField()

# URL
website = models.URLField()

# Slug (URL-friendly text)
slug = models.SlugField(unique=True)
```

### Number Fields

```python
# Integer
age = models.IntegerField()

# Positive integer
quantity = models.PositiveIntegerField()

# Decimal (for currency)
price = models.DecimalField(max_digits=10, decimal_places=2)

# Float
rating = models.FloatField()
```

### Date/Time Fields

```python
# Date only
birth_date = models.DateField()

# Time only
start_time = models.TimeField()

# Date and time (auto-set on creation)
created_at = models.DateTimeField(auto_now_add=True)

# Date and time (auto-set on every save)
updated_at = models.DateTimeField(auto_now=True)

# Date and time (editable)
published_at = models.DateTimeField(null=True, blank=True)
```

### Boolean Fields

```python
# Boolean
is_active = models.BooleanField(default=True)

# NullBoolean (deprecated, use BooleanField with null=True)
status = models.BooleanField(null=True, blank=True)
```

### File Fields

```python
# File upload
document = models.FileField(upload_to='documents/')

# Image upload
avatar = models.ImageField(upload_to='avatars/')

# With file type validation
from django.core.validators import FileExtensionValidator
image = models.ImageField(
    upload_to='images/',
    validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif'])]
)
```

### Relationship Fields

```python
# ForeignKey (many-to-one)
author = models.ForeignKey(
    User,
    on_delete=models.CASCADE,
    related_name='articles'
)

# ManyToMany
tags = models.ManyToManyField(Tag, blank=True, related_name='articles')

# OneToOne
profile = models.OneToOneField(User, on_delete=models.CASCADE)
```

## Field Options

```python
# Required field
title = models.CharField(max_length=100)

# Optional field (allows NULL)
description = models.TextField(null=True, blank=True)

# With default value
status = models.CharField(max_length=20, default='draft')

# With choices
STATUS_CHOICES = [
    ('draft', 'Draft'),
    ('published', 'Published'),
]
status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

# With validators
from django.core.validators import MinValueValidator, MaxValueValidator
rating = models.IntegerField(
    validators=[MinValueValidator(1), MaxValueValidator(5)]
)

# Unique constraint
email = models.EmailField(unique=True)

# With help text
bio = models.TextField(help_text='Tell us about yourself')

# With error messages
name = models.CharField(
    max_length=100,
    error_messages={'blank': 'Name is required'}
)
```

## Meta Options

```python
class Meta:
    # Ordering
    ordering = ['-created_at', 'title']
    
    # Database table name
    db_table = 'articles'
    
    # Verbose names
    verbose_name = 'article'
    verbose_name_plural = 'articles'
    
    # Constraints
    constraints = [
        models.UniqueConstraint(fields=['title', 'author'], name='unique_article')
    ]
    
    # Indexes
    indexes = [
        models.Index(fields=['-created_at']),
        models.Index(fields=['title'], name='title_idx'),
    ]
    
    # Permissions
    permissions = [
        ('can_publish', 'Can publish articles'),
    ]
    
    # Abstract base class
    abstract = True
```

## Model Methods

```python
class Article(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, default='draft')
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        # Custom save logic
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('article_detail', kwargs={'slug': self.slug})
    
    @property
    def is_published(self):
        return self.status == 'published'
    
    @classmethod
    def get_published(cls):
        return cls.objects.filter(status='published')
```

## Managers

```python
class PublishedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status='published')

class Article(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
    ]
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=20, default='draft')
    
    objects = models.Manager()  # Default manager
    published = PublishedManager()  # Custom manager
    
    class Meta:
        ordering = ['-created_at']

# Usage
Article.objects.all()  # All articles
Article.published.all()  # Only published articles
```

## Inheritance

### Abstract Base Classes

```python
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True

class Article(TimeStampedModel):
    title = models.CharField(max_length=200)

class Comment(TimeStampedModel):
    content = models.TextField()
```

### Multi-table Inheritance

```python
class Place(models.Model):
    name = models.CharField(max_length=100)

class Restaurant(Place):
    serves_pizza = models.BooleanField(default=False)

# Creates two tables with a one-to-one link
```

### Proxy Models

```python
class Article(models.Model):
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=20)

class PublishedArticle(Article):
    class Meta:
        proxy = True
        ordering = ['-created_at']
    
    def publish(self):
        self.status = 'published'
        self.save()
```

## Relationships

### ForeignKey

```python
class Article(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,  # Delete articles when user is deleted
        related_name='articles',  # user.articles.all()
        related_query_name='article',  # user.article_set.filter()
    )

# Usage
article.author  # Get author
user.articles.all()  # Get all user's articles
Article.objects.filter(author=user)  # Filter by author
```

### ManyToMany

```python
class Article(models.Model):
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name='articles',
        through='ArticleTag'  # Custom through model
    )

class ArticleTag(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

# Usage
article.tags.all()  # Get all tags
tag.articles.all()  # Get all articles with this tag
article.tags.add(tag1, tag2)  # Add tags
article.tags.remove(tag1)  # Remove tag
article.tags.clear()  # Remove all tags
article.tags.set([tag1, tag2])  # Set tags
```

### OneToOne

```python
class User(models.Model):
    username = models.CharField(max_length=100)

class Profile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
    )
    bio = models.TextField()

# Usage
user.profile  # Get profile
profile.user  # Get user
```

## Queries

### Creating Objects

```python
# Create and save
article = Article(title='Hello', content='World')
article.save()

# Create in one step
article = Article.objects.create(title='Hello', content='World')

# Get or create
article, created = Article.objects.get_or_create(
    title='Hello',
    defaults={'content': 'World'}
)
```

### Reading Objects

```python
# Get all
Article.objects.all()

# Get one
Article.objects.get(pk=1)
Article.objects.get(slug='hello')

# Filter
Article.objects.filter(status='published')
Article.objects.filter(author=user, status='published')

# Exclude
Article.objects.exclude(status='draft')

# Order by
Article.objects.order_by('-created_at')
Article.objects.order_by('title', '-created_at')
```

### Chaining Queries

```python
# Complex queries
Article.objects.filter(
    status='published',
    author__is_active=True
).exclude(
    title__icontains='test'
).order_by('-created_at')[:10]
```

### Aggregation

```python
from django.db.models import Count, Avg, Sum, Max, Min

# Count
Article.objects.count()
Article.objects.filter(status='published').count()

# Aggregate
Article.objects.aggregate(avg_rating=Avg('rating'))

# Annotate
Article.objects.annotate(comment_count=Count('comments'))
```

### Q Objects

```python
from django.db.models import Q

# OR
Article.objects.filter(Q(title__icontains='django') | Q(content__icontains='django'))

# AND
Article.objects.filter(Q(status='published') & Q(author=user))

# NOT
Article.objects.filter(~Q(status='draft'))
```

### F Objects

```python
from django.db.models import F

# Update based on other fields
Article.objects.update(rating=F('rating') + 1)

# Compare fields
Article.objects.filter(rating__gt=F('views'))
```

## Signals

```python
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

@receiver(pre_save, sender=Article)
def pre_save_article(sender, instance, **kwargs):
    if not instance.slug:
        from django.utils.text import slugify
        instance.slug = slugify(instance.title)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
```

## Best Practices

1. **Always define `__str__`** - Makes debugging easier
2. **Use `related_name`** - Makes reverse relationships explicit
3. **Use `Meta.ordering`** - Default ordering for queries
4. **Use `related_query_name`** - For filtering in queries
5. **Use `abstract = True`** - For base classes
6. **Use `through`** - For ManyToMany with extra fields
7. **Use `on_delete`** - Always specify cascade behavior
8. **Use `null=True, blank=True`** - For optional fields
9. **Use `default`** - For default values
10. **Use `validators`** - For data validation
