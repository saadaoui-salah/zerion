# Next.js Examples

## App Router Examples

### Basic Page
```tsx
// app/page.tsx
export default function HomePage() {
  return (
    <div className="container mx-auto py-10">
      <h1 className="text-4xl font-bold">Welcome to Next.js</h1>
      <p className="mt-4 text-muted-foreground">
        Build modern web applications with App Router
      </p>
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

### Dynamic Route
```tsx
// app/blog/[slug]/page.tsx
import { db } from "@/lib/db"
import { notFound } from "next/navigation"

interface BlogPostProps {
  params: { slug: string }
}

export async function generateMetadata({ params }: BlogPostProps) {
  const post = await db.post.findUnique({
    where: { slug: params.slug },
  })

  if (!post) return { title: "Post Not Found" }

  return {
    title: post.title,
    description: post.excerpt,
  }
}

export default async function BlogPost({ params }: BlogPostProps) {
  const post = await db.post.findUnique({
    where: { slug: params.slug },
  })

  if (!post) notFound()

  return (
    <article className="container mx-auto py-10">
      <h1 className="text-4xl font-bold">{post.title}</h1>
      <p className="mt-4 text-muted-foreground">{post.excerpt}</p>
      <div className="mt-8 prose">{post.content}</div>
    </article>
  )
}
```

### Loading State
```tsx
// app/dashboard/loading.tsx
export default function DashboardLoading() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary"></div>
    </div>
  )
}
```

### Error Boundary
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

## Server Components

### Data Fetching
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
    <div className="container mx-auto py-10">
      <h1 className="text-4xl font-bold mb-8">Posts</h1>
      <div className="grid gap-4 md:grid-cols-2">
        {posts.map((post) => (
          <article key={post.id} className="rounded-lg border p-4">
            <h2 className="text-xl font-bold">{post.title}</h2>
            <p className="text-muted-foreground">{post.excerpt}</p>
          </article>
        ))}
      </div>
    </div>
  )
}
```

### Database Query
```tsx
// app/users/page.tsx
import { db } from "@/lib/db"

export default async function UsersPage() {
  const users = await db.user.findMany()

  return (
    <div className="container mx-auto py-10">
      <h1 className="text-4xl font-bold mb-8">Users</h1>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {users.map((user) => (
          <div key={user.id} className="rounded-lg border p-4">
            <h2 className="text-xl font-bold">{user.name}</h2>
            <p className="text-muted-foreground">{user.email}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
```

## Client Components

### Interactive Counter
```tsx
// components/counter.tsx
"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"

export function Counter() {
  const [count, setCount] = useState(0)

  return (
    <div className="flex items-center gap-4">
      <Button onClick={() => setCount(count - 1)}>-</Button>
      <span className="text-2xl font-bold">{count}</span>
      <Button onClick={() => setCount(count + 1)}>+</Button>
    </div>
  )
}
```

### Theme Toggle
```tsx
// components/theme-toggle.tsx
"use client"

import { useTheme } from "next-themes"
import { Button } from "@/components/ui/button"
import { Moon, Sun } from "lucide-react"

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

### Search Input
```tsx
// components/search-input.tsx
"use client"

import { useState } from "react"
import { Input } from "@/components/ui/input"
import { Search } from "lucide-react"

export function SearchInput() {
  const [query, setQuery] = useState("")

  return (
    <div className="relative">
      <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
      <Input
        placeholder="Search..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="pl-8"
      />
    </div>
  )
}
```

## Server Actions

### Basic Form
```tsx
// app/login/page.tsx
import { login } from "@/app/actions"

export default function LoginPage() {
  return (
    <div className="container mx-auto py-10 max-w-md">
      <h1 className="text-4xl font-bold mb-8">Login</h1>
      <form action={login} className="space-y-4">
        <div>
          <label htmlFor="email" className="block text-sm font-medium">
            Email
          </label>
          <input
            type="email"
            id="email"
            name="email"
            required
            className="w-full rounded-md border p-2 mt-1"
          />
        </div>
        <div>
          <label htmlFor="password" className="block text-sm font-medium">
            Password
          </label>
          <input
            type="password"
            id="password"
            name="password"
            required
            className="w-full rounded-md border p-2 mt-1"
          />
        </div>
        <button
          type="submit"
          className="w-full rounded-md bg-primary text-primary-foreground p-2"
        >
          Login
        </button>
      </form>
    </div>
  )
}
```

### Server Action with Validation
```tsx
// app/actions.ts
"use server"

import { revalidatePath } from "next/cache"
import { redirect } from "next/navigation"
import { z } from "zod"

const PostSchema = z.object({
  title: z.string().min(1),
  content: z.string().min(10),
})

export async function createPost(formData: FormData) {
  const result = PostSchema.safeParse({
    title: formData.get("title"),
    content: formData.get("content"),
  })

  if (!result.success) {
    return { errors: result.error.flatten().fieldErrors }
  }

  await db.post.create({
    data: result.data,
  })

  revalidatePath("/posts")
  redirect("/posts")
}
```

### Form with useActionState
```tsx
// components/create-post-form.tsx
"use client"

import { useActionState } from "react"
import { createPost } from "@/app/actions"

export function CreatePostForm() {
  const [state, formAction, isPending] = useActionState(createPost, null)

  return (
    <form action={formAction} className="space-y-4">
      <div>
        <label htmlFor="title" className="block text-sm font-medium">
          Title
        </label>
        <input
          type="text"
          id="title"
          name="title"
          required
          className="w-full rounded-md border p-2 mt-1"
        />
        {state?.errors?.title && (
          <p className="text-sm text-red-500 mt-1">{state.errors.title[0]}</p>
        )}
      </div>
      <div>
        <label htmlFor="content" className="block text-sm font-medium">
          Content
        </label>
        <textarea
          id="content"
          name="content"
          required
          rows={4}
          className="w-full rounded-md border p-2 mt-1"
        />
        {state?.errors?.content && (
          <p className="text-sm text-red-500 mt-1">{state.errors.content[0]}</p>
        )}
      </div>
      <button
        type="submit"
        disabled={isPending}
        className="w-full rounded-md bg-primary text-primary-foreground p-2 disabled:opacity-50"
      >
        {isPending ? "Creating..." : "Create Post"}
      </button>
    </form>
  )
}
```

## API Routes

### Basic Route Handler
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

### Route with Params
```tsx
// app/api/users/[id]/route.ts
import { NextResponse } from "next/server"
import { db } from "@/lib/db"

interface RouteContext {
  params: { id: string }
}

export async function GET(request: Request, { params }: RouteContext) {
  const user = await db.user.findUnique({
    where: { id: params.id },
  })

  if (!user) {
    return NextResponse.json({ error: "User not found" }, { status: 404 })
  }

  return NextResponse.json(user)
}

export async function PUT(request: Request, { params }: RouteContext) {
  const body = await request.json()
  const user = await db.user.update({
    where: { id: params.id },
    data: body,
  })

  return NextResponse.json(user)
}

export async function DELETE(request: Request, { params }: RouteContext) {
  await db.user.delete({
    where: { id: params.id },
  })

  return NextResponse.json({ success: true })
}
```

## Authentication

### Sign In Page
```tsx
// app/auth/signin/page.tsx
import { SignInForm } from "@/components/auth/signin-form"

export default function SignInPage() {
  return (
    <div className="container mx-auto py-10 max-w-md">
      <h1 className="text-4xl font-bold mb-8">Sign In</h1>
      <SignInForm />
    </div>
  )
}
```

### Sign In Form
```tsx
// components/auth/signin-form.tsx
"use client"

import { signIn } from "next-auth/react"
import { useRouter } from "next/navigation"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export function SignInForm() {
  const router = useRouter()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    const result = await signIn("credentials", {
      email,
      password,
      redirect: false,
    })

    if (result?.error) {
      setError("Invalid credentials")
    } else {
      router.push("/dashboard")
      router.refresh()
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && <p className="text-red-500">{error}</p>}
      <div>
        <label htmlFor="email" className="block text-sm font-medium">
          Email
        </label>
        <Input
          type="email"
          id="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </div>
      <div>
        <label htmlFor="password" className="block text-sm font-medium">
          Password
        </label>
        <Input
          type="password"
          id="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </div>
      <Button type="submit" className="w-full">
        Sign In
      </Button>
    </form>
  )
}
```

### Protected Dashboard
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
    <div className="container mx-auto py-10">
      <h1 className="text-4xl font-bold mb-8">Dashboard</h1>
      <p>Welcome, {session.user.name}!</p>
    </div>
  )
}
```

## Parallel Routes

### Modal Pattern
```tsx
// app/dashboard/layout.tsx
export default function DashboardLayout({
  children,
  modal,
}: {
  children: React.ReactNode
  modal: React.ReactNode
}) {
  return (
    <div>
      {children}
      {modal}
    </div>
  )
}

// app/dashboard/@modal/(.)feed/[id]/page.tsx
export default function InterceptedPost() {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center">
      <div className="bg-background rounded-lg p-6 max-w-md">
        <h2 className="text-2xl font-bold">Post Details</h2>
      </div>
    </div>
  )
}
```

## Streaming with Suspense

### Loading States
```tsx
// app/dashboard/page.tsx
import { Suspense } from "react"
import { Analytics } from "@/components/analytics"
import { RecentPosts } from "@/components/recent-posts"

export default function DashboardPage() {
  return (
    <div className="container mx-auto py-10">
      <h1 className="text-4xl font-bold mb-8">Dashboard</h1>
      <div className="grid grid-cols-2 gap-4">
        <Suspense fallback={<div className="animate-pulse bg-muted h-64 rounded-lg" />}>
          <Analytics />
        </Suspense>
        <Suspense fallback={<div className="animate-pulse bg-muted h-64 rounded-lg" />}>
          <RecentPosts />
        </Suspense>
      </div>
    </div>
  )
}
```

## Image Optimization

### Optimized Image
```tsx
import Image from "next/image"

export function HeroImage() {
  return (
    <div className="relative aspect-video">
      <Image
        src="/images/hero.jpg"
        alt="Hero image"
        fill
        className="object-cover"
        priority
        placeholder="blur"
        blurDataURL="data:image/jpeg;base64,..."
      />
    </div>
  )
}
```

## Font Optimization

### Custom Fonts
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

## Metadata

### Basic Metadata
```tsx
// app/page.tsx
import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "My App",
  description: "Built with Next.js",
}

export default function HomePage() {
  return <div>Home</div>
}
```

### Dynamic Metadata
```tsx
// app/blog/[slug]/page.tsx
import type { Metadata } from "next"

interface BlogPostProps {
  params: { slug: string }
}

export async function generateMetadata({ params }: BlogPostProps): Promise<Metadata> {
  const post = await getPost(params.slug)

  return {
    title: post.title,
    description: post.excerpt,
    openGraph: {
      title: post.title,
      description: post.excerpt,
      images: [post.coverImage],
    },
  }
}
```

## Testing

### Unit Test
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

### E2E Test
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
