# Tailwind CSS Setup Guide

## Installation

### 1. Install Tailwind CSS

#### Using npm
```bash
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

#### Using yarn
```bash
yarn add -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

#### Using pnpm
```bash
pnpm add -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

### 2. Configure tailwind.config.js

```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
```

### 3. Create CSS Variables (globals.css)

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --popover: 0 0% 100%;
    --popover-foreground: 222.2 84% 4.9%;
    --primary: 222.2 47.4% 11.2%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 222.2 84% 4.9%;
    --radius: 0.5rem;
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --card: 222.2 84% 4.9%;
    --card-foreground: 210 40% 98%;
    --popover: 222.2 84% 4.9%;
    --popover-foreground: 210 40% 98%;
    --primary: 210 40% 98%;
    --primary-foreground: 222.2 47.4% 11.2%;
    --secondary: 217.2 32.6% 17.5%;
    --secondary-foreground: 210 40% 98%;
    --muted: 217.2 32.6% 17.5%;
    --muted-foreground: 215 20.2% 65.1%;
    --accent: 217.2 32.6% 17.5%;
    --accent-foreground: 210 40% 98%;
    --destructive: 0 62.8% 30.6%;
    --destructive-foreground: 210 40% 98%;
    --border: 217.2 32.6% 17.5%;
    --input: 217.2 32.6% 17.5%;
    --ring: 212.7 26.8% 83.9%;
  }
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
  }
}
```

### 4. Add Tailwind to Your CSS Entry Point

```css
/* In your main CSS file */
@import "tailwindcss/base";
@import "tailwindcss/components";
@import "tailwindcss/utilities";
```

## Framework-Specific Setup

### React/Next.js Setup

1. **Install dependencies:**
```bash
npm install -D tailwindcss postcss autoprefixer
npm install class-variance-authority clsx tailwind-merge
npm install tailwindcss-animate
```

2. **Create postcss.config.js:**
```javascript
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

3. **Update next.config.js:**
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable Tailwind CSS
  experimental: {
    optimizeCss: true,
  },
}

module.exports = nextConfig
```

4. **Add to _app.tsx:**
```tsx
import "@/styles/globals.css"
import type { AppProps } from "next/app"

export default function App({ Component, pageProps }: AppProps) {
  return <Component {...pageProps} />
}
```

### Django Setup

1. **Install django-tailwind:**
```bash
pip install django-tailwind
# or
pip install django-tailwind-cli
```

2. **Add to INSTALLED_APPS:**
```python
INSTALLED_APPS = [
    # ...
    'tailwind',
]
```

3. **Configure settings.py:**
```python
TAILWIND_APP_NAME = 'tailwind'
TAILWIND_CSS_PATH = 'css/styles.css'

# Optional: Auto-detect changes
TAILWIND_AUTO_COMPILE = True
```

4. **Add to urls.py:**
```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('tailwind/', include('tailwind.urls')),
]
```

5. **Run migrations:**
```bash
python manage.py tailwind init
python manage.py tailwind install
python manage.py tailwind start
```

6. **Add to base template:**
```html
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}My App{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'css/styles.css' %}">
</head>
<body class="min-h-screen bg-background font-sans antialiased">
  {% block content %}{% endblock %}
</body>
</html>
```

## Utility Functions

### cn() Function (React/Next.js)

Create a utility function for merging class names:

```typescript
// lib/utils.ts
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

### Django Template Filters

Create custom template filters for dynamic classes:

```python
# templatetags/tailwind_filters.py
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def tailwind_classes(value):
    """Convert a dictionary to Tailwind classes."""
    if isinstance(value, dict):
        classes = []
        for key, val in value.items():
            if val:
                classes.append(key)
        return mark_safe(' '.join(classes))
    return value

@register.filter
def conditional_class(condition, classes):
    """Return classes if condition is true."""
    if condition:
        return mark_safe(classes)
    return ''
```

## Build Process

### Development

```bash
# React/Next.js
npm run dev

# Django
python manage.py tailwind start
```

### Production

```bash
# React/Next.js
npm run build

# Django
python manage.py collectstatic
python manage.py tailwind build
```

## Deployment

### Vercel (Next.js)

1. Connect your repository
2. Vercel auto-detects Next.js
3. Deploy automatically

### Netlify

1. Connect your repository
2. Set build command: `npm run build`
3. Set publish directory: `.next` (Next.js) or `build` (React)

### Heroku (Django)

1. Add buildpack:
```bash
heroku buildpacks:add https://github.com/heroku/heroku-buildpack-nodejs
heroku buildpacks:add https://github.com/heroku/heroku-buildpack-python
```

2. Add Procfile:
```
web: gunicorn myproject.wsgi
```

3. Deploy:
```bash
git push heroku main
```

## Troubleshooting

### Common Issues

1. **Styles not applying:**
   - Check if Tailwind is in your content paths
   - Verify CSS variables are defined
   - Ensure postcss.config.js exists

2. **Dark mode not working:**
   - Add `darkMode: ["class"]` to tailwind.config.js
   - Add `class="dark"` to HTML element
   - Use `dark:` variants in your classes

3. **Build errors:**
   - Clear node_modules and reinstall
   - Check for conflicting PostCSS plugins
   - Verify Tailwind version compatibility

4. **Django static files not found:**
   - Run `python manage.py collectstatic`
   - Check STATIC_URL and STATICFILES_DIRS
   - Verify TAILWIND_CSS_PATH setting

## Resources

- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [shadcn/ui Components](https://ui.shadcn.com/)
- [Radix UI Primitives](https://www.radix-ui.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [Django Documentation](https://docs.djangoproject.com/)
