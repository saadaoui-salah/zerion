# Next.js Expert Memory

## Key Learnings

### App Router
- Use App Router for new projects (recommended over Pages Router)
- Server Components are the default
- Add "use client" only when needed
- Use loading.tsx for loading states
- Implement error.tsx for error boundaries
- Use not-found.tsx for 404 pages

### Server Components
- Fetch data directly in components
- Access backend resources (database, file system)
- Keep sensitive data server-side
- Reduce client-side JavaScript
- Automatic code splitting

### Client Components
- Use "use client" directive at top of file
- Interactive UI elements (forms, buttons, modals)
- Browser APIs (localStorage, window)
- Event handlers (onClick, onChange)
- React hooks (useState, useEffect, useContext)

### Server Actions
- Form handling without API routes
- Direct database mutations
- Progressive enhancement
- Automatic revalidation
- Type-safe with TypeScript

## Common Patterns

### Layout Pattern
```tsx
// app/dashboard/layout.tsx
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

### Server Action Pattern
```tsx
// app/actions.ts
"use server"

import { revalidatePath } from "next/cache"
import { redirect } from "next/navigation"
import { z } from "zod"

const FormSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
})

export async function login(formData: FormData) {
  const validatedFields = FormSchema.safeParse({
    email: formData.get("email"),
    password: formData.get("password"),
  })

  if (!validatedFields.success) {
    return { error: "Invalid fields" }
  }

  await authenticate(validatedFields.data)
  
  revalidatePath("/dashboard")
  redirect("/dashboard")
}
```

### Dynamic Route Pattern
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
    <article>
      <h1>{post.title}</h1>
      <p>{post.content}</p>
    </article>
  )
}
```

## Performance Tips

### Image Optimization
```tsx
import Image from "next/image"

<Image
  src="/hero.jpg"
  alt="Hero"
  width={1200}
  height={600}
  priority
  placeholder="blur"
  blurDataURL="data:image/jpeg;base64,..."
/>
```

### Font Optimization
```tsx
import { Inter } from "next/font/google"

const inter = Inter({ subsets: ["latin"] })

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

### Dynamic Imports
```tsx
import dynamic from "next/dynamic"

const HeavyComponent = dynamic(() => import("./heavy-component"), {
  loading: () => <p>Loading...</p>,
  ssr: false,
})
```

## Authentication

### NextAuth.js
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

## Troubleshooting

### Common Issues
1. **Hydration errors**: Ensure server and client render the same content
2. **Styles not applying**: Check Tailwind content paths and CSS variables
3. **Build errors**: Clear .next directory and reinstall dependencies
4. **404 errors**: Check file naming conventions and route structure

### Solutions
1. **Clear cache**: `rm -rf .next && npm run dev`
2. **Reinstall dependencies**: `rm -rf node_modules && npm install`
3. **Check TypeScript**: `npx tsc --noEmit`
4. **Run linter**: `npm run lint`

## Best Practices

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
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [shadcn/ui Components](https://ui.shadcn.com/)
