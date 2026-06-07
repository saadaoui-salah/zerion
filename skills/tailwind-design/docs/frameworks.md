# Framework-Specific Tailwind Integration

## Django Integration

### Project Structure
```
myproject/
├── myproject/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── myapp/
│   ├── templates/
│   │   ├── base.html
│   │   ├── components/
│   │   │   ├── button.html
│   │   │   ├── card.html
│   │   │   └── header.html
│   │   └── myapp/
│   │       └── index.html
│   ├── templatetags/
│   │   └── tailwind_filters.py
│   └── views.py
├── static/
│   ├── css/
│   │   └── styles.css
│   └── js/
├── tailwind.config.js
├── postcss.config.js
└── manage.py
```

### Installation
```bash
pip install django-tailwind
# or
pip install django-tailwind-cli
```

### Settings Configuration
```python
# settings.py
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Custom apps
    'myapp',
    # Tailwind
    'tailwind',
]

TAILWIND_APP_NAME = 'tailwind'
TAILWIND_CSS_PATH = 'css/styles.css'

# Optional settings
TAILWIND_AUTO_COMPILE = True
TAILWIND_USE_MODERN = True
```

### URL Configuration
```python
# urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('tailwind/', include('tailwind.urls')),
    path('', include('myapp.urls')),
]
```

### Template Components

#### base.html
```html
{% load static %}
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}My App{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'css/styles.css' %}">
  {% block extra_css %}{% endblock %}
</head>
<body class="min-h-screen bg-background font-sans antialiased">
  <div class="relative flex min-h-screen flex-col">
    {% include "components/header.html" %}
    <main class="flex-1">
      {% block content %}{% endblock %}
    </main>
    {% include "components/footer.html" %}
  </div>
  {% block extra_js %}{% endblock %}
</body>
</html>
```

#### components/button.html
```html
{% load static %}
<button
  class="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 {{ variant_classes }} {{ size_classes }} {{ custom_classes }}"
  {% if type %}type="{{ type }}"{% endif %}
  {% if disabled %}disabled{% endif %}
  {% if onclick %}onclick="{{ onclick }}"{% endif %}
>
  {% if icon_left %}
    <span class="mr-2">{{ icon_left }}</span>
  {% endif %}
  {{ label }}
  {% if icon_right %}
    <span class="ml-2">{{ icon_right }}</span>
  {% endif %}
</button>
```

#### components/card.html
```html
<div class="rounded-lg border bg-card text-card-foreground shadow-sm {{ custom_classes }}">
  {% if title or description %}
    <div class="flex flex-col space-y-1.5 p-6">
      {% if title %}
        <h3 class="text-2xl font-semibold leading-none tracking-tight">{{ title }}</h3>
      {% endif %}
      {% if description %}
        <p class="text-sm text-muted-foreground">{{ description }}</p>
      {% endif %}
    </div>
  {% endif %}
  <div class="p-6 pt-0">
    {{ content }}
  </div>
  {% if footer %}
    <div class="flex items-center p-6 pt-0">
      {{ footer }}
    </div>
  {% endif %}
</div>
```

### Template Filters
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

### Usage in Templates
```html
{% extends "base.html" %}
{% load tailwind_filters %}

{% block content %}
<div class="container mx-auto py-10">
  {% include "components/card.html" with title="Welcome" description="Get started with your project" content="<p>This is the card content</p>" footer="<button class='...'>Action</button>" %}
  
  <!-- Using template filter -->
  <div class="{% tailwind_classes {'bg-primary': is_primary, 'text-white': is_primary} %}">
    Dynamic content
  </div>
</div>
{% endblock %}
```

---

## React Integration

### Project Structure
```
my-react-app/
├── src/
│   ├── components/
│   │   ├── ui/
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── input.tsx
│   │   │   └── index.ts
│   │   ├── layout/
│   │   │   ├── header.tsx
│   │   │   ├── footer.tsx
│   │   │   └── sidebar.tsx
│   │   └── App.tsx
│   ├── lib/
│   │   └── utils.ts
│   ├── styles/
│   │   └── globals.css
│   └── index.tsx
├── tailwind.config.js
├── postcss.config.js
├── package.json
└── tsconfig.json
```

### Installation
```bash
npx create-react-app my-app --template typescript
cd my-app
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install class-variance-authority clsx tailwind-merge
npm install tailwindcss-animate
npm install @radix-ui/react-*  # For specific components
```

### Utility Functions
```typescript
// src/lib/utils.ts
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

### Component Examples

#### Button Component
```tsx
// src/components/ui/button.tsx
import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
```

#### Card Component
```tsx
// src/components/ui/card.tsx
import * as React from "react"
import { cn } from "@/lib/utils"

const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-lg border bg-card text-card-foreground shadow-sm",
      className
    )}
    {...props}
  />
))
Card.displayName = "Card"

const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col space-y-1.5 p-6", className)}
    {...props}
  />
))
CardHeader.displayName = "CardHeader"

const CardTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn(
      "text-2xl font-semibold leading-none tracking-tight",
      className
    )}
    {...props}
  />
))
CardTitle.displayName = "CardTitle"

const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
))
CardDescription.displayName = "CardDescription"

const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
))
CardContent.displayName = "CardContent"

const CardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex items-center p-6 pt-0", className)}
    {...props}
  />
))
CardFooter.displayName = "CardFooter"

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }
```

### Usage
```tsx
// src/App.tsx
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

function App() {
  return (
    <div className="container mx-auto py-10">
      <Card>
        <CardHeader>
          <CardTitle>Welcome</CardTitle>
          <CardDescription>Get started with your project</CardDescription>
        </CardHeader>
        <CardContent>
          <Button>Get Started</Button>
        </CardContent>
      </Card>
    </div>
  )
}

export default App
```

---

## Next.js Integration

### Project Structure
```
my-next-app/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   ├── globals.css
│   └── dashboard/
│       ├── page.tsx
│       └── layout.tsx
├── components/
│   ├── ui/
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   └── index.ts
│   ├── layout/
│   │   ├── header.tsx
│   │   ├── footer.tsx
│   │   └── sidebar.tsx
│   └── theme-provider.tsx
├── lib/
│   └── utils.ts
├── tailwind.config.js
├── postcss.config.js
├── package.json
└── next.config.js
```

### Installation
```bash
npx create-next-app@latest my-app --typescript --tailwind --eslint --app --src-dir
cd my-app
npm install class-variance-authority clsx tailwind-merge
npm install tailwindcss-animate
npm install @radix-ui/react-*  # For specific components
npm install next-themes  # For dark mode
```

### Layout Configuration
```tsx
// app/layout.tsx
import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { ThemeProvider } from "@/components/theme-provider"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "My App",
  description: "Built with Next.js and Tailwind CSS",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          {children}
        </ThemeProvider>
      </body>
    </html>
  )
}
```

### Theme Provider
```tsx
// components/theme-provider.tsx
"use client"

import * as React from "react"
import { ThemeProvider as NextThemesProvider } from "next-themes"
import { type ThemeProviderProps } from "next-themes/dist/types"

export function ThemeProvider({ children, ...props }: ThemeProviderProps) {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>
}
```

### Page Examples
```tsx
// app/page.tsx
import { Metadata } from "next"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export const metadata: Metadata = {
  title: "Home",
  description: "Welcome to my app",
}

export default function HomePage() {
  return (
    <div className="container mx-auto py-10">
      <Card>
        <CardHeader>
          <CardTitle>Welcome</CardTitle>
          <CardDescription>Get started with your project</CardDescription>
        </CardHeader>
        <CardContent>
          <Button>Get Started</Button>
        </CardContent>
      </Card>
    </div>
  )
}
```

### Dashboard Layout
```tsx
// app/dashboard/layout.tsx
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <Header />
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  )
}
```

### Server Components
```tsx
// app/dashboard/page.tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export default function DashboardPage() {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader>
          <CardTitle>Total Revenue</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">$45,231.89</div>
        </CardContent>
      </Card>
      {/* More cards */}
    </div>
  )
}
```

### Client Components
```tsx
// components/interactive-chart.tsx
"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function InteractiveChart() {
  const [data, setData] = useState([])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Interactive Chart</CardTitle>
      </CardHeader>
      <CardContent>
        <Button onClick={() => fetchData()}>Refresh Data</Button>
        {/* Chart component */}
      </CardContent>
    </Card>
  )
}
```

### Image Optimization
```tsx
// components/optimized-image.tsx
import Image from "next/image"
import { Card, CardContent } from "@/components/ui/card"

export function OptimizedImage() {
  return (
    <Card>
      <CardContent className="p-0">
        <div className="relative aspect-video">
          <Image
            src="/images/hero.jpg"
            alt="Hero image"
            fill
            className="object-cover rounded-t-lg"
            priority
          />
        </div>
      </CardContent>
    </Card>
  )
}
```

### Font Optimization
```tsx
// app/layout.tsx
import { Inter, Playfair_Display } from "next/font/google"

const inter = Inter({ subsets: ["latin"] })
const playfair = Playfair_Display({ subsets: ["latin"] })

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={`${inter.className} antialiased`}>
        <h1 className={playfair.className}>Beautiful Typography</h1>
        {children}
      </body>
    </html>
  )
}
```

### Data Fetching
```tsx
// app/posts/page.tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

async function getPosts() {
  const res = await fetch("https://api.example.com/posts", {
    next: { revalidate: 3600 }, // ISR: revalidate every hour
  })
  return res.json()
}

export default async function PostsPage() {
  const posts = await getPosts()

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {posts.map((post) => (
        <Card key={post.id}>
          <CardHeader>
            <CardTitle>{post.title}</CardTitle>
          </CardHeader>
          <CardContent>
            <p>{post.excerpt}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
```

---

## Comparison

### Django vs React vs Next.js

| Feature | Django | React | Next.js |
|---------|--------|-------|---------|
| SSR | Yes (templates) | No (client) | Yes (App Router) |
| SSG | No | No | Yes |
| ISR | No | No | Yes |
| API Routes | Yes | No | Yes |
| File-based Routing | No | No | Yes |
| SEO | Good | Poor | Excellent |
| Complexity | Medium | Low | Medium |
| Best For | Content sites | SPAs | Full-stack apps |

### When to Use What

- **Django**: Content-heavy sites, admin panels, traditional web apps
- **React**: Single-page applications, dashboards, interactive UIs
- **Next.js**: Full-stack applications, e-commerce, blogs, marketing sites
