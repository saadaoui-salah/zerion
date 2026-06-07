# Tailwind Design Workflow

## Overview
This workflow guides you through creating beautiful, accessible UI components using Tailwind CSS with shadcn-like patterns for Django, React, and Next.js projects.

## Step 1: Project Analysis

### 1.1 Identify Framework
```bash
# Check for Django
if [ -f "manage.py" ]; then
  FRAMEWORK="django"
fi

# Check for React/Next.js
if [ -f "package.json" ]; then
  if grep -q "next" package.json; then
    FRAMEWORK="nextjs"
  else
    FRAMEWORK="react"
  fi
fi
```

### 1.2 Check Tailwind Installation
```bash
# Check if Tailwind is installed
if [ -f "tailwind.config.js" ] || [ -f "tailwind.config.ts" ]; then
  echo "Tailwind is configured"
else
  echo "Tailwind needs to be installed"
fi
```

### 1.3 Analyze Existing Styles
- Review existing CSS files
- Check for custom color schemes
- Identify design system patterns
- Note accessibility requirements

## Step 2: Setup & Configuration

### 2.1 Install Dependencies

#### Django
```bash
pip install django-tailwind
# or
pip install django-tailwind-cli

# Add to INSTALLED_APPS
INSTALLED_APPS = [
    ...
    'tailwind',
]

# Add to settings.py
TAILWIND_APP_NAME = 'tailwind'
TAILWIND_CSS_PATH = 'css/styles.css'
```

#### React/Next.js
```bash
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p

# Install shadcn dependencies
npm install class-variance-authority clsx tailwind-merge
npm install @radix-ui/react-*  # For specific components
```

### 2.2 Configure Tailwind

#### tailwind.config.js
```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    // For Django
    "./templates/**/*.html",
    "./**/templates/**/*.html",
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

### 2.3 CSS Variables

#### globals.css
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

## Step 3: Component Creation

### 3.1 Utility Functions

#### lib/utils.ts (React/Next.js)
```typescript
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

### 3.2 Base Components

#### Button Component
```tsx
// components/ui/button.tsx
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
// components/ui/card.tsx
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

### 3.3 Django Template Components

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

## Step 4: Responsive Design

### 4.1 Mobile-First Approach
```tsx
// Mobile-first responsive design
<div className="w-full md:w-1/2 lg:w-1/3 p-4">
  {/* Content */}
</div>

// Responsive grid
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {/* Grid items */}
</div>

// Responsive typography
<h1 className="text-2xl md:text-3xl lg:text-4xl font-bold">
  Responsive Title
</h1>
```

### 4.2 Container Queries
```css
/* When supported */
.card-container {
  container-type: inline-size;
}

@container (min-width: 400px) {
  .card-content {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
}
```

## Step 5: Dark Mode Implementation

### 5.1 Theme Provider (React/Next.js)
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

### 5.2 Theme Toggle
```tsx
// components/theme-toggle.tsx
"use client"

import * as React from "react"
import { Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"
import { Button } from "@/components/ui/button"

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  return (
    <Button
      variant="outline"
      size="icon"
      onClick={() => setTheme(theme === "light" ? "dark" : "light")}
    >
      <Sun className="h-[1.2rem] w-[1.2rem] rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
      <Moon className="absolute h-[1.2rem] w-[1.2rem] rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
      <span className="sr-only">Toggle theme</span>
    </Button>
  )
}
```

## Step 6: Accessibility

### 6.1 Focus Management
```tsx
// Focus visible styles
<button className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
  Accessible Button
</button>

// Skip to main content
<a
  href="#main-content"
  className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-4 focus:bg-background"
>
  Skip to main content
</a>
```

### 6.2 ARIA Attributes
```tsx
// Proper ARIA labels
<button aria-label="Close dialog" onClick={onClose}>
  <X className="h-4 w-4" />
</button>

// Live regions for dynamic content
<div aria-live="polite" aria-atomic="true">
  {notification && <p>{notification}</p>}
</div>

// Proper roles
<nav role="navigation" aria-label="Main navigation">
  {/* Navigation items */}
</nav>
```

## Step 7: Performance Optimization

### 7.1 Purge Configuration
```javascript
// tailwind.config.js
module.exports = {
  content: [
    // Only include files that actually use Tailwind classes
    "./src/**/*.{js,ts,jsx,tsx}",
    "./pages/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  // Enable JIT mode for better performance
  future: {
    hoverOnlyWhenSupported: true,
  },
}
```

### 7.2 Code Splitting
```tsx
// Dynamic imports for heavy components
import dynamic from "next/dynamic"

const HeavyComponent = dynamic(() => import("./heavy-component"), {
  loading: () => <p>Loading...</p>,
  ssr: false,
})
```

## Step 8: Testing

### 8.1 Visual Regression Testing
```bash
# Install Chromatic or similar tool
npm install -D @chromatic-com/storybook

# Run visual tests
npx chromatic --project-token=YOUR_TOKEN
```

### 8.2 Accessibility Testing
```bash
# Install axe-core
npm install -D @axe-core/react

# Run in development
if (process.env.NODE_ENV !== "production") {
  const axe = require("@axe-core/react")
  axe(React, ReactDOM, 1000)
}
```

## Step 9: Documentation

### 9.1 Storybook Setup
```bash
# Install Storybook
npx storybook@latest init

# Create stories for components
// Button.stories.tsx
import type { Meta, StoryObj } from "@storybook/react"
import { Button } from "./button"

const meta: Meta<typeof Button> = {
  title: "UI/Button",
  component: Button,
  tags: ["autodocs"],
  argTypes: {
    variant: {
      control: "select",
      options: ["default", "destructive", "outline", "secondary", "ghost", "link"],
    },
    size: {
      control: "select",
      options: ["default", "sm", "lg", "icon"],
    },
  },
}

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    children: "Button",
  },
}
```

### 9.2 Component Documentation
```markdown
# Button Component

A versatile button component with multiple variants and sizes.

## Usage

```tsx
import { Button } from "@/components/ui/button"

<Button>Default Button</Button>
<Button variant="destructive">Destructive</Button>
<Button size="lg">Large Button</Button>
```

## Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| variant | "default" \| "destructive" \| "outline" \| "secondary" \| "ghost" \| "link" | "default" | The visual style variant |
| size | "default" \| "sm" \| "lg" \| "icon" | "default" | The size of the button |
| asChild | boolean | false | Render as child element |
```

## Step 10: Deployment

### 10.1 Build Optimization
```bash
# Next.js
npm run build

# Django
python manage.py collectstatic
python manage.py tailwind build
```

### 10.2 CDN Configuration
```html
<!-- Use CDN for production -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/tailwindcss@3.4.1/lib/tailwindcss.min.css">
```

## Remember

1. Always start with mobile-first design
2. Use semantic HTML elements
3. Implement proper focus states
4. Support dark mode
5. Test across browsers and devices
6. Document component usage
7. Optimize for performance
8. Ensure accessibility compliance
