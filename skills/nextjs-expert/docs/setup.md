# Next.js Setup Guide

## Installation

### 1. Create New Project

```bash
npx create-next-app@latest my-app
```

### 2. Project Options

```bash
npx create-next-app@latest my-app --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"
```

### 3. Manual Setup

```bash
mkdir my-app
cd my-app
npm init -y
npm install next react react-dom
npm install -D typescript @types/node @types/react @types/react-dom
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

## Configuration

### next.config.js
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "github.com",
      },
    ],
  },
  experimental: {
    serverActions: true,
  },
}

module.exports = nextConfig
```

### tsconfig.json
```json
{
  "compilerOptions": {
    "target": "es5",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

### tailwind.config.js
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
    },
  },
  plugins: [require("tailwindcss-animate")],
}
```

### postcss.config.js
```javascript
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

## Project Structure

### App Router Structure
```
my-app/
├── app/
│   ├── layout.tsx          # Root layout
│   ├── page.tsx            # Home page
│   ├── loading.tsx         # Loading UI
│   ├── error.tsx           # Error boundary
│   ├── not-found.tsx       # 404 page
│   ├── globals.css         # Global styles
│   ├── dashboard/
│   │   ├── layout.tsx      # Dashboard layout
│   │   ├── page.tsx        # Dashboard page
│   │   └── settings/
│   │       └── page.tsx    # Settings page
│   └── api/
│       └── users/
│           └── route.ts    # API route
├── components/
│   ├── ui/                 # Reusable UI components
│   └── layout/             # Layout components
├── lib/
│   ├── utils.ts            # Utility functions
│   ├── db.ts               # Database client
│   └── auth.ts             # Authentication config
├── public/                 # Static assets
├── tailwind.config.js
├── postcss.config.js
├── next.config.js
├── tsconfig.json
└── package.json
```

## Essential Dependencies

### Core
```bash
npm install next react react-dom
```

### TypeScript
```bash
npm install -D typescript @types/node @types/react @types/react-dom
```

### Tailwind CSS
```bash
npm install -D tailwindcss postcss autoprefixer
npm install tailwindcss-animate
```

### UI Components
```bash
npm install class-variance-authority clsx tailwind-merge
npm install @radix-ui/react-*  # For specific components
```

### Forms
```bash
npm install react-hook-form @hookform/resolvers zod
```

### Authentication
```bash
npm install next-auth @auth/core
```

### Database
```bash
npm install prisma @prisma/client
```

### State Management
```bash
npm install zustand
```

### Testing
```bash
npm install -D @testing-library/react @testing-library/jest-dom jest
npm install -D @playwright/test
```

## Development

### Start Development Server
```bash
npm run dev
```

### Build for Production
```bash
npm run build
```

### Start Production Server
```bash
npm start
```

### Run Linter
```bash
npm run lint
```

## Environment Variables

### .env.local
```bash
# Database
DATABASE_URL="postgresql://user:password@localhost:5432/mydb"

# Authentication
NEXTAUTH_SECRET="your-secret-here"
NEXTAUTH_URL="http://localhost:3000"

# API Keys
OPENAI_API_KEY="your-api-key"
```

### Accessing Environment Variables
```typescript
// Server-side
const dbUrl = process.env.DATABASE_URL

// Client-side (must prefix with NEXT_PUBLIC_)
const apiKey = process.env.NEXT_PUBLIC_API_KEY
```

## Deployment

### Vercel (Recommended)
1. Push to GitHub
2. Import project in Vercel
3. Configure environment variables
4. Deploy

### Docker
```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY . .
RUN npm ci
RUN npm run build

FROM node:18-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./
RUN npm ci --only=production
CMD ["npm", "start"]
```

### Netlify
1. Connect your repository
2. Set build command: `npm run build`
3. Set publish directory: `.next`

## Troubleshooting

### Common Issues

1. **Styles not applying:**
   - Check if Tailwind is in your content paths
   - Verify CSS variables are defined
   - Ensure postcss.config.js exists

2. **Build errors:**
   - Clear .next directory: `rm -rf .next`
   - Reinstall dependencies: `rm -rf node_modules && npm install`
   - Check TypeScript errors: `npx tsc --noEmit`

3. **Hydration errors:**
   - Ensure server and client render the same content
   - Use "use client" for interactive components
   - Avoid browser-only APIs in server components

4. **404 errors:**
   - Check file naming conventions
   - Verify route structure
   - Ensure proper exports

### Solutions

1. **Clear cache:**
```bash
rm -rf .next
npm run dev
```

2. **Reinstall dependencies:**
```bash
rm -rf node_modules
npm install
```

3. **Check TypeScript:**
```bash
npx tsc --noEmit
```

4. **Run linter:**
```bash
npm run lint
```

## Resources

- [Next.js Documentation](https://nextjs.org/docs)
- [App Router Migration Guide](https://nextjs.org/docs/app/building-your-application/upgrading/app-router-migration)
- [React Server Components](https://react.dev/reference/rsc/server-components)
- [Server Actions](https://nextjs.org/docs/app/building-your-application/data-fetching/server-actions-and-mutations)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [shadcn/ui Components](https://ui.shadcn.com/)
