# UI/UX Design Examples

## Design Tokens

```css
:root {
  /* Colors */
  --color-primary-50: #eff6ff;
  --color-primary-100: #dbeafe;
  --color-primary-500: #3b82f6;
  --color-primary-600: #2563eb;
  --color-primary-700: #1d4ed8;

  --color-neutral-50: #f8fafc;
  --color-neutral-100: #f1f5f9;
  --color-neutral-900: #0f172a;

  --color-success: #22c55e;
  --color-warning: #f59e0b;
  --color-error: #ef4444;

  /* Typography */
  --font-sans: 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;

  --text-xs: 0.75rem;    /* 12px */
  --text-sm: 0.875rem;   /* 14px */
  --text-base: 1rem;     /* 16px */
  --text-lg: 1.125rem;   /* 18px */
  --text-xl: 1.25rem;    /* 20px */
  --text-2xl: 1.5rem;    /* 24px */
  --text-3xl: 1.875rem;  /* 30px */

  /* Spacing (4px grid) */
  --space-0: 0;
  --space-1: 0.25rem;    /* 4px */
  --space-2: 0.5rem;     /* 8px */
  --space-3: 0.75rem;    /* 12px */
  --space-4: 1rem;       /* 16px */
  --space-6: 1.5rem;     /* 24px */
  --space-8: 2rem;       /* 32px */
  --space-12: 3rem;      /* 48px */

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);

  /* Radius */
  --radius-sm: 0.25rem;
  --radius-md: 0.375rem;
  --radius-lg: 0.5rem;
  --radius-full: 9999px;

  /* Transitions */
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-normal: 200ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-slow: 300ms cubic-bezier(0.4, 0, 0.2, 1);
}

/* Dark mode */
@media (prefers-color-scheme: dark) {
  :root {
    --color-neutral-50: #0f172a;
    --color-neutral-900: #f8fafc;
  }
}
```

## Accessible Button Component

```tsx
import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        primary: 'bg-primary-600 text-white hover:bg-primary-700 focus-visible:ring-primary-500',
        secondary: 'bg-neutral-100 text-neutral-900 hover:bg-neutral-200 focus-visible:ring-neutral-400',
        ghost: 'hover:bg-neutral-100 focus-visible:ring-neutral-400',
        danger: 'bg-error text-white hover:bg-red-700 focus-visible:ring-red-500',
      },
      size: {
        sm: 'h-8 px-3 text-sm',
        md: 'h-10 px-4 text-base',
        lg: 'h-12 px-6 text-lg',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  }
);

interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, loading, children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(buttonVariants({ variant, size, className }))}
        disabled={disabled || loading}
        aria-busy={loading}
        {...props}
      >
        {loading && (
          <svg
            className="mr-2 h-4 w-4 animate-spin"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';

export { Button, buttonVariants };
```

## Responsive Layout

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Responsive Layout</title>
  <style>
    *, *::before, *::after {
      box-sizing: border-box;
      margin: 0;
    }

    body {
      font-family: var(--font-sans);
      line-height: 1.6;
      color: var(--color-neutral-900);
    }

    .layout {
      display: grid;
      grid-template-columns: 1fr;
      min-height: 100vh;
    }

    @media (min-width: 768px) {
      .layout {
        grid-template-columns: 250px 1fr;
      }
    }

    @media (min-width: 1024px) {
      .layout {
        grid-template-columns: 280px 1fr 300px;
      }
    }

    .sidebar {
      display: none;
      background: var(--color-neutral-50);
      border-right: 1px solid var(--color-neutral-100);
      padding: var(--space-4);
    }

    @media (min-width: 768px) {
      .sidebar { display: block; }
    }

    .main {
      padding: var(--space-4);
    }

    @media (min-width: 768px) {
      .main { padding: var(--space-6); }
    }

    .aside {
      display: none;
      background: var(--color-neutral-50);
      border-left: 1px solid var(--color-neutral-100);
      padding: var(--space-4);
    }

    @media (min-width: 1024px) {
      .aside { display: block; }
    }

    /* Fluid typography */
    h1 {
      font-size: clamp(1.5rem, 4vw, 2.5rem);
      line-height: 1.2;
    }
  </style>
</head>
<body>
  <div class="layout">
    <nav class="sidebar" aria-label="Main navigation">
      <h2>Menu</h2>
      <!-- Navigation items -->
    </nav>
    <main class="main" role="main">
      <h1>Page Title</h1>
      <!-- Content -->
    </main>
    <aside class="aside" aria-label="Related content">
      <h2>Related</h2>
      <!-- Sidebar content -->
    </aside>
  </div>
</body>
</html>
```

## Accessible Modal Dialog

```tsx
import { useEffect, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}

export function Modal({ open, onClose, title, children }: ModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (open) {
      previousFocus.current = document.activeElement as HTMLElement;
      dialog.showModal();
    } else {
      dialog.close();
      previousFocus.current?.focus();
    }
  }, [open]);

  return createPortal(
    <dialog
      ref={dialogRef}
      onClose={onClose}
      aria-labelledby="modal-title"
      className="fixed inset-0 z-50 w-full max-w-md rounded-lg bg-white p-0 shadow-lg backdrop:bg-black/50 open:flex open:items-center open:justify-center"
    >
      <div className="p-6">
        <h2 id="modal-title" className="text-xl font-semibold">
          {title}
        </h2>
        <div className="mt-4">
          {children}
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="rounded-md px-4 py-2 text-sm font-medium hover:bg-neutral-100"
          >
            Cancel
          </button>
          <button
            onClick={onClose}
            className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            Confirm
          </button>
        </div>
      </div>
    </dialog>,
    document.body
  );
}
```

## Form Validation UX

```tsx
import { useState, type FormEvent } from 'react';

interface FormErrors {
  email?: string;
  password?: string;
}

export function LoginForm() {
  const [errors, setErrors] = useState<FormErrors>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  function validate(email: string, password: string): FormErrors {
    const errors: FormErrors = {};

    if (!email) {
      errors.email = 'Email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.email = 'Please enter a valid email';
    }

    if (!password) {
      errors.password = 'Password is required';
    } else if (password.length < 8) {
      errors.password = 'Password must be at least 8 characters';
    }

    return errors;
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const email = formData.get('email') as string;
    const password = formData.get('password') as string;

    const validationErrors = validate(email, password);
    setErrors(validationErrors);

    if (Object.keys(validationErrors).length === 0) {
      // Submit form
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <div className="space-y-4">
        <div>
          <label htmlFor="email" className="block text-sm font-medium">
            Email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            required
            aria-invalid={!!errors.email}
            aria-describedby={errors.email ? 'email-error' : undefined}
            onBlur={() => setTouched({ ...touched, email: true })}
            className="mt-1 block w-full rounded-md border px-3 py-2 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          {errors.email && (
            <p id="email-error" className="mt-1 text-sm text-error" role="alert">
              {errors.email}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="password" className="block text-sm font-medium">
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            required
            minLength={8}
            aria-invalid={!!errors.password}
            aria-describedby={errors.password ? 'password-error' : 'password-hint'}
            className="mt-1 block w-full rounded-md border px-3 py-2 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <p id="password-hint" className="mt-1 text-sm text-neutral-500">
            Must be at least 8 characters
          </p>
          {errors.password && (
            <p id="password-error" className="mt-1 text-sm text-error" role="alert">
              {errors.password}
            </p>
          )}
        </div>

        <button
          type="submit"
          className="w-full rounded-md bg-primary-600 px-4 py-2 font-medium text-white hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
        >
          Sign in
        </button>
      </div>
    </form>
  );
}
```

## Skeleton Loading State

```tsx
function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded bg-neutral-200 ${className}`}
      aria-hidden="true"
    />
  );
}

export function CardSkeleton() {
  return (
    <div className="rounded-lg border p-4" role="status" aria-label="Loading content">
      <div className="flex items-center gap-3">
        <Skeleton className="h-10 w-10 rounded-full" />
        <div className="flex-1">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="mt-1 h-3 w-1/4" />
        </div>
      </div>
      <Skeleton className="mt-4 h-20 w-full" />
      <div className="mt-4 flex gap-2">
        <Skeleton className="h-8 w-20" />
        <Skeleton className="h-8 w-20" />
      </div>
      <span className="sr-only">Loading...</span>
    </div>
  );
}
```
