# Next.js Development Workflow

## Overview
This workflow guides you through building modern Next.js applications with App Router, Server Components, Server Actions, and best practices.

## Step 1: Project Setup

### 1.1 Create New Project
```bash
npx create-next-app@latest my-app --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"
```

### 1.2 Project Structure
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

### 1.3 Install Dependencies
```bash
# Essential
npm install next react react-dom

# UI Components
npm install class-variance-authority clsx tailwind-merge
npm install tailwindcss-animate
npm install @radix-ui/react-*  # For specific components

# Forms
npm install react-hook-form @hookform/resolvers zod

# Authentication
npm install next-auth @auth/core

# Database
npm install prisma @prisma/client

# State Management
npm install zustand

# Testing
npm install -D @testing-library/react @testing-library/jest-dom jest
npm install -D @playwright/test
```

## Step 2: Configuration

### 2.1 next.config.js
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

### 2.2 TypeScript Configuration
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

### 2.3 Tailwind Configuration
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

## Step 3: Core Components

### 3.1 Utility Functions
```typescript
// lib/utils.ts
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

### 3.2 Root Layout
```tsx
// app/layout.tsx
import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "My App",
  description: "Built with Next.js",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>{children}</body>
    </html>
  )
}
```

### 3.3 Global Styles
```css
/* app/globals.css */
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

## Step 4: Data Fetching

### 4.1 Server Component Fetching
```tsx
// app/posts/page.tsx
import { db } from "@/lib/db"

async function getPosts() {
  const res = await fetch("https://api.example.com/posts", {
    next: { revalidate: 3600 },
  })
  return res.json()
}

export default async function PostsPage() {
  const posts = await getPosts()

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {posts.map((post) => (
        <article key={post.id} className="rounded-lg border p-4">
          <h2 className="text-xl font-bold">{post.title}</h2>
          <p className="text-muted-foreground">{post.excerpt}</p>
        </article>
      ))}
    </div>
  )
}
```

### 4.2 Route Handlers
```tsx
// app/api/users/route.ts
import { NextResponse } from "next/server"
import { db } from "@/lib/db"

export async function GET() {
  const users = await db.user.findMany()
  return NextResponse.json(users)
}

export async function POST(request: Request) {
  const body = await request.json()
  const user = await db.user.create({ data: body })
  return NextResponse.json(user, { status: 201 })
}
```

### 4.3 Streaming with Suspense
```tsx
// app/dashboard/page.tsx
import { Suspense } from "react"
import { Analytics } from "@/components/analytics"
import { RecentPosts } from "@/components/recent-posts"

export default function DashboardPage() {
  return (
    <div>
      <h1>Dashboard</h1>
      <div className="grid grid-cols-2 gap-4">
        <Suspense fallback={<div>Loading analytics...</div>}>
          <Analytics />
        </Suspense>
        <Suspense fallback={<div>Loading posts...</div>}>
          <RecentPosts />
        </Suspense>
      </div>
    </div>
  )
}
```

## Step 5: Forms with Server Actions

### 5.1 Basic Form
```tsx
// app/login/page.tsx
import { login } from "@/app/actions"

export default function LoginPage() {
  return (
    <form action={login} className="space-y-4">
      <div>
        <label htmlFor="email">Email</label>
        <input
          type="email"
          id="email"
          name="email"
          required
          className="w-full rounded-md border p-2"
        />
      </div>
      <div>
        <label htmlFor="password">Password</label>
        <input
          type="password"
          id="password"
          name="password"
          required
          className="w-full rounded-md border p-2"
        />
      </div>
      <button
        type="submit"
        className="w-full rounded-md bg-primary text-primary-foreground p-2"
      >
        Login
      </button>
    </form>
  )
}
```

### 5.2 Server Action
```tsx
// app/actions.ts
"use server"

import { revalidatePath } from "next/cache"
import { redirect } from "next/navigation"
import { z } from "zod"

const LoginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
})

export async function login(formData: FormData) {
  const result = LoginSchema.safeParse({
    email: formData.get("email"),
    password: formData.get("password"),
  })

  if (!result.success) {
    return { error: "Invalid fields" }
  }

  await authenticate(result.data)
  revalidatePath("/dashboard")
  redirect("/dashboard")
}
```

### 5.3 Form with Validation
```tsx
// components/signup-form.tsx
"use client"

import { useActionState } from "react"
import { signup } from "@/app/actions"

export function SignupForm() {
  const [state, formAction, isPending] = useActionState(signup, null)

  return (
    <form action={formAction} className="space-y-4">
      <div>
        <label htmlFor="name">Name</label>
        <input
          type="text"
          id="name"
          name="name"
          required
          className="w-full rounded-md border p-2"
        />
        {state?.errors?.name && (
          <p className="text-sm text-red-500">{state.errors.name[0]}</p>
        )}
      </div>
      <div>
        <label htmlFor="email">Email</label>
        <input
          type="email"
          id="email"
          name="email"
          required
          className="w-full rounded-md border p-2"
        />
        {state?.errors?.email && (
          <p className="text-sm text-red-500">{state.errors.email[0]}</p>
        )}
      </div>
      <button
        type="submit"
        disabled={isPending}
        className="w-full rounded-md bg-primary text-primary-foreground p-2 disabled:opacity-50"
      >
        {isPending ? "Loading..." : "Sign Up"}
      </button>
    </form>
  )
}
```

## Step 6: Authentication

### 6.1 NextAuth Configuration
```typescript
// lib/auth.ts
import { NextAuthOptions } from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"
import { PrismaAdapter } from "@auth/prisma-adapter"
import { db } from "./db"

export const authOptions: NextAuthOptions = {
  adapter: PrismaAdapter(db),
  providers: [
    CredentialsProvider({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          throw new Error("Invalid credentials")
        }

        const user = await db.user.findUnique({
          where: { email: credentials.email },
        })

        if (!user || !user?.hashedPassword) {
          throw new Error("Invalid credentials")
        }

        const isCorrectPassword = await compare(
          credentials.password,
          user.hashedPassword
        )

        if (!isCorrectPassword) {
          throw new Error("Invalid credentials")
        }

        return user
      },
    }),
  ],
  session: {
    strategy: "jwt",
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id
      }
      return token
    },
    async session({ session, token }) {
      if (token) {
        session.user.id = token.id as string
      }
      return session
    },
  },
  pages: {
    signIn: "/auth/signin",
  },
}
```

### 6.2 Auth API Route
```typescript
// app/api/auth/[...nextauth]/route.ts
import NextAuth from "next-auth"
import { authOptions } from "@/lib/auth"

const handler = NextAuth(authOptions)
export { handler as GET, handler as POST }
```

### 6.3 Protected Page
```tsx
// app/dashboard/page.tsx
import { getServerSession } from "next-auth"
import { redirect } from "next/navigation"
import { authOptions } from "@/lib/auth"

export default async function DashboardPage() {
  const session = await getServerSession(authOptions)

  if (!session) {
    redirect("/api/auth/signin")
  }

  return (
    <div>
      <h1>Welcome, {session.user.name}</h1>
    </div>
  )
}
```

### 6.4 Middleware Protection
```typescript
// middleware.ts
import { withAuth } from "next-auth/middleware"

export default withAuth({
  pages: {
    signIn: "/auth/signin",
  },
})

export const config = {
  matcher: ["/dashboard/:path*"],
}
```

## Step 7: Error Handling

### 7.1 Error Boundary
```tsx
// app/dashboard/error.tsx
"use client"

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px]">
      <h2 className="text-2xl font-bold mb-4">Something went wrong!</h2>
      <p className="text-muted-foreground mb-4">{error.message}</p>
      <button
        onClick={() => reset()}
        className="rounded-md bg-primary text-primary-foreground px-4 py-2"
      >
        Try again
      </button>
    </div>
  )
}
```

### 7.2 Not Found
```tsx
// app/not-found.tsx
import Link from "next/link"

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px]">
      <h2 className="text-2xl font-bold mb-4">Not Found</h2>
      <p className="text-muted-foreground mb-4">
        Could not find the requested resource.
      </p>
      <Link
        href="/"
        className="rounded-md bg-primary text-primary-foreground px-4 py-2"
      >
        Return Home
      </Link>
    </div>
  )
}
```

## Step 8: Testing

### 8.1 Unit Tests
```tsx
// __tests__/button.test.tsx
import { render, screen } from "@testing-library/react"
import { Button } from "@/components/ui/button"

describe("Button", () => {
  it("renders correctly", () => {
    render(<Button>Click me</Button>)
    expect(screen.getByRole("button")).toHaveTextContent("Click me")
  })

  it("can be disabled", () => {
    render(<Button disabled>Click me</Button>)
    expect(screen.getByRole("button")).toBeDisabled()
  })
})
```

### 8.2 E2E Tests
```typescript
// e2e/home.spec.ts
import { test, expect } from "@playwright/test"

test("homepage has title", async ({ page }) => {
  await page.goto("/")
  await expect(page).toHaveTitle("My App")
})

test("can navigate to dashboard", async ({ page }) => {
  await page.goto("/")
  await page.click('a[href="/dashboard"]')
  await expect(page).toHaveURL("/dashboard")
})
```

## Step 9: Deployment

### 9.1 Vercel Deployment
1. Push to GitHub
2. Import project in Vercel
3. Configure environment variables
4. Deploy

### 9.2 Docker Deployment
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

### 9.3 Environment Variables
```bash
# .env.local
DATABASE_URL="postgresql://..."
NEXTAUTH_SECRET="your-secret"
NEXTAUTH_URL="http://localhost:3000"
```

## Step 10: Best Practices

### Do's
- Use Server Components by default
- Add "use client" only when needed
- Use Server Actions for form handling
- Implement proper error boundaries
- Use loading.tsx for loading states
- Optimize images with next/image
- Use next/font for fonts
- Implement proper SEO with metadata

### Don'ts
- Don't overuse client components
- Don't fetch data in useEffect when possible
- Don't ignore TypeScript errors
- Don't skip error handling
- Don't forget to revalidate paths after mutations
- Don't use window/document in server components
- Don't store sensitive data in client components

## Resources

- [Next.js Documentation](https://nextjs.org/docs)
- [App Router Migration Guide](https://nextjs.org/docs/app/building-your-application/upgrading/app-router-migration)
- [React Server Components](https://react.dev/reference/rsc/server-components)
- [Server Actions](https://nextjs.org/docs/app/building-your-application/data-fetching/server-actions-and-mutations)
