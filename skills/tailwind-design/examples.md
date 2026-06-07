# Tailwind Design Examples

## Button Examples

### Basic Buttons
```tsx
// Default button
<Button>Click me</Button>

// Destructive button
<Button variant="destructive">Delete</Button>

// Outline button
<Button variant="outline">Cancel</Button>

// Secondary button
<Button variant="secondary">Save</Button>

// Ghost button
<Button variant="ghost">Hover me</Button>

// Link button
<Button variant="link">Learn more</Button>
```

### Button Sizes
```tsx
// Small button
<Button size="sm">Small</Button>

// Default button
<Button size="default">Default</Button>

// Large button
<Button size="lg">Large</Button>

// Icon button
<Button size="icon">
  <Plus className="h-4 w-4" />
</Button>
```

### Button with Icons
```tsx
// Button with left icon
<Button>
  <Mail className="mr-2 h-4 w-4" /> Login with Email
</Button>

// Button with right icon
<Button>
  Next <ArrowRight className="ml-2 h-4 w-4" />
</Button>

// Icon-only button
<Button variant="outline" size="icon">
  <Settings className="h-4 w-4" />
</Button>
```

### Django Template Button
```html
{% load static %}

<!-- Default button -->
<button class="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2">
  Click me
</button>

<!-- Destructive button -->
<button class="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-destructive text-destructive-foreground hover:bg-destructive/90 h-10 px-4 py-2">
  Delete
</button>

<!-- Button with icon -->
<button class="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2">
  <svg class="mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
  </svg>
  Add Item
</button>
```

## Card Examples

### Basic Card
```tsx
<Card>
  <CardHeader>
    <CardTitle>Card Title</CardTitle>
    <CardDescription>Card description goes here</CardDescription>
  </CardHeader>
  <CardContent>
    <p>This is the card content. You can put anything here.</p>
  </CardContent>
  <CardFooter>
    <Button>Action</Button>
  </CardFooter>
</Card>
```

### Card with Image
```tsx
<Card className="overflow-hidden">
  <img 
    src="/images/hero.jpg" 
    alt="Hero image" 
    className="w-full h-48 object-cover"
  />
  <CardHeader>
    <CardTitle>Image Card</CardTitle>
    <CardDescription>Card with an image on top</CardDescription>
  </CardHeader>
  <CardContent>
    <p>This card has an image at the top.</p>
  </CardContent>
</Card>
```

### Interactive Card
```tsx
<Card className="cursor-pointer transition-all hover:shadow-lg hover:-translate-y-1">
  <CardHeader>
    <CardTitle>Interactive Card</CardTitle>
    <CardDescription>Hover to see the effect</CardDescription>
  </CardHeader>
  <CardContent>
    <p>This card has hover effects.</p>
  </CardContent>
</Card>
```

### Django Template Card
```html
<div class="rounded-lg border bg-card text-card-foreground shadow-sm">
  <div class="flex flex-col space-y-1.5 p-6">
    <h3 class="text-2xl font-semibold leading-none tracking-tight">Card Title</h3>
    <p class="text-sm text-muted-foreground">Card description goes here</p>
  </div>
  <div class="p-6 pt-0">
    <p>This is the card content. You can put anything here.</p>
  </div>
  <div class="flex items-center p-6 pt-0">
    <button class="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2">
      Action
    </button>
  </div>
</div>
```

## Form Examples

### Input Fields
```tsx
// Basic input
<Input type="text" placeholder="Enter your name" />

// Input with label
<div className="space-y-2">
  <Label htmlFor="email">Email</Label>
  <Input id="email" type="email" placeholder="you@example.com" />
</div>

// Input with description
<div className="space-y-2">
  <Label htmlFor="password">Password</Label>
  <Input id="password" type="password" />
  <p className="text-sm text-muted-foreground">
    Must be at least 8 characters long
  </p>
</div>

// Disabled input
<Input disabled placeholder="Disabled input" />
```

### Select
```tsx
<Select>
  <SelectTrigger className="w-full">
    <SelectValue placeholder="Select a fruit" />
  </SelectTrigger>
  <SelectContent>
    <SelectItem value="apple">Apple</SelectItem>
    <SelectItem value="banana">Banana</SelectItem>
    <SelectItem value="orange">Orange</SelectItem>
  </SelectContent>
</Select>
```

### Checkbox and Radio
```tsx
// Checkbox
<div className="flex items-center space-x-2">
  <Checkbox id="terms" />
  <Label htmlFor="terms" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
    Accept terms and conditions
  </Label>
</div>

// Radio group
<RadioGroup defaultValue="comfortable">
  <div className="flex items-center space-x-2">
    <RadioGroupItem value="default" id="r1" />
    <Label htmlFor="r1">Default</Label>
  </div>
  <div className="flex items-center space-x-2">
    <RadioGroupItem value="comfortable" id="r2" />
    <Label htmlFor="r2">Comfortable</Label>
  </div>
  <div className="flex items-center space-x-2">
    <RadioGroupItem value="compact" id="r3" />
    <Label htmlFor="r3">Compact</Label>
  </div>
</RadioGroup>
```

### Switch
```tsx
<div className="flex items-center space-x-2">
  <Switch id="airplane-mode" />
  <Label htmlFor="airplane-mode">Airplane Mode</Label>
</div>
```

### Django Template Form
```html
<form class="space-y-4">
  <!-- Input -->
  <div class="space-y-2">
    <label for="name" class="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
      Name
    </label>
    <input
      type="text"
      id="name"
      class="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
      placeholder="Enter your name"
    />
  </div>

  <!-- Select -->
  <div class="space-y-2">
    <label for="fruit" class="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
      Fruit
    </label>
    <select
      id="fruit"
      class="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
    >
      <option value="">Select a fruit</option>
      <option value="apple">Apple</option>
      <option value="banana">Banana</option>
      <option value="orange">Orange</option>
    </select>
  </div>

  <!-- Textarea -->
  <div class="space-y-2">
    <label for="message" class="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
      Message
    </label>
    <textarea
      id="message"
      class="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
      placeholder="Enter your message"
    ></textarea>
  </div>

  <!-- Checkbox -->
  <div class="flex items-center space-x-2">
    <input
      type="checkbox"
      id="terms"
      class="peer h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
    />
    <label for="terms" class="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
      Accept terms and conditions
    </label>
  </div>

  <button type="submit" class="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2">
    Submit
  </button>
</form>
```

## Navigation Examples

### Header Navigation
```tsx
<header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
  <div className="container flex h-14 items-center">
    <div className="mr-4 hidden md:flex">
      <a href="/" className="mr-6 flex items-center space-x-2">
        <Logo className="h-6 w-6" />
        <span className="hidden font-bold sm:inline-block">My App</span>
      </a>
      <nav className="flex items-center space-x-6 text-sm font-medium">
        <a href="/features" className="transition-colors hover:text-foreground/80 text-foreground/60">Features</a>
        <a href="/pricing" className="transition-colors hover:text-foreground/80 text-foreground/60">Pricing</a>
        <a href="/docs" className="transition-colors hover:text-foreground/80 text-foreground/60">Docs</a>
      </nav>
    </div>
    <div className="flex flex-1 items-center justify-between space-x-2 md:justify-end">
      <div className="w-full flex-1 md:w-auto md:flex-none">
        <Button variant="outline" className="inline-flex items-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground h-9 px-4 py-2 relative w-full justify-start text-sm text-muted-foreground sm:pr-12 md:w-40 lg:w-64">
          <span className="hidden lg:inline-flex">Search documentation...</span>
          <span className="inline-flex lg:hidden">Search...</span>
          <kbd className="pointer-events-none absolute right-1.5 top-1.5 hidden h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium opacity-100 sm:flex">
            <span className="text-xs">⌘</span>K
          </kbd>
        </Button>
      </div>
      <nav className="flex items-center gap-2">
        <Button variant="ghost" size="icon">
          <GitHub className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon">
          <Twitter className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon">
          <ThemeToggle />
        </Button>
      </nav>
    </div>
  </div>
</header>
```

### Sidebar Navigation
```tsx
<aside className="hidden w-[250px] flex-col md:flex">
  <nav className="grid items-start gap-2 text-sm">
    <a href="/dashboard" className="flex items-center gap-3 rounded-lg bg-accent px-3 py-2 text-accent-foreground transition-all hover:text-accent-foreground">
      <Home className="h-4 w-4" />
      Dashboard
    </a>
    <a href="/dashboard/analytics" className="flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:bg-accent hover:text-accent-foreground">
      <BarChart className="h-4 w-4" />
      Analytics
    </a>
    <a href="/dashboard/settings" className="flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:bg-accent hover:text-accent-foreground">
      <Settings className="h-4 w-4" />
      Settings
    </a>
  </nav>
</aside>
```

### Mobile Navigation
```tsx
<Sheet>
  <SheetTrigger asChild>
    <Button variant="outline" size="icon" className="md:hidden">
      <Menu className="h-5 w-5" />
    </Button>
  </SheetTrigger>
  <SheetContent side="left">
    <nav className="grid gap-6 text-lg font-medium">
      <a href="/" className="flex items-center gap-2 text-lg font-semibold">
        <Logo className="h-6 w-6" />
        <span className="sr-only">My App</span>
      </a>
      <a href="/features" className="transition-colors hover:text-foreground text-muted-foreground">Features</a>
      <a href="/pricing" className="transition-colors hover:text-foreground text-muted-foreground">Pricing</a>
      <a href="/docs" className="transition-colors hover:text-foreground text-muted-foreground">Docs</a>
    </nav>
  </SheetContent>
</Sheet>
```

## Layout Examples

### Hero Section
```tsx
<section className="container grid items-center gap-6 pb-8 pt-6 md:py-10">
  <div className="flex max-w-[980px] flex-col items-center gap-2">
    <h1 className="text-center text-3xl font-bold leading-tight tracking-tighter md:text-5xl lg:leading-[1.1]">
      Beautiful UI Components
      <br className="hidden sm:block" />
      Built with Tailwind CSS
    </h1>
    <p className="max-w-[700px] text-center text-lg text-muted-foreground sm:text-xl">
      A collection of accessible and customizable components for your next project.
    </p>
  </div>
  <div className="flex gap-4 justify-center">
    <Button size="lg">Get Started</Button>
    <Button variant="outline" size="lg">Documentation</Button>
  </div>
</section>
```

### Features Grid
```tsx
<section className="container py-8 md:py-12 lg:py-24">
  <div className="mx-auto flex max-w-[58rem] flex-col items-center justify-center gap-4 text-center">
    <h2 className="text-3xl font-bold leading-[1.1] sm:text-3xl md:text-5xl">Features</h2>
    <p className="max-w-[85%] leading-normal text-muted-foreground sm:text-lg sm:leading-7">
      Everything you need to build modern web applications
    </p>
  </div>
  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
    {features.map((feature) => (
      <Card key={feature.title} className="overflow-hidden">
        <CardHeader>
          <CardTitle>{feature.title}</CardTitle>
          <CardDescription>{feature.description}</CardDescription>
        </CardHeader>
        <CardContent>
          <img src={feature.image} alt={feature.title} className="w-full rounded-md" />
        </CardContent>
      </Card>
    ))}
  </div>
</section>
```

### Pricing Table
```tsx
<section className="container py-8 md:py-12 lg:py-24">
  <div className="mx-auto flex max-w-[58rem] flex-col items-center justify-center gap-4 text-center">
    <h2 className="text-3xl font-bold leading-[1.1] sm:text-3xl md:text-5xl">Pricing</h2>
    <p className="max-w-[85%] leading-normal text-muted-foreground sm:text-lg sm:leading-7">
      Choose the plan that's right for you
    </p>
  </div>
  <div className="grid gap-4 md:grid-cols-3">
    {/* Free Plan */}
    <Card>
      <CardHeader>
        <CardTitle>Free</CardTitle>
        <CardDescription>For personal projects</CardDescription>
        <div className="mt-4">
          <span className="text-4xl font-bold">$0</span>
          <span className="text-muted-foreground">/month</span>
        </div>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2 text-sm">
          <li className="flex items-center">
            <Check className="mr-2 h-4 w-4 text-primary" />
            1 project
          </li>
          <li className="flex items-center">
            <Check className="mr-2 h-4 w-4 text-primary" />
            Basic features
          </li>
          <li className="flex items-center">
            <Check className="mr-2 h-4 w-4 text-primary" />
            Community support
          </li>
        </ul>
      </CardContent>
      <CardFooter>
        <Button className="w-full" variant="outline">Get Started</Button>
      </CardFooter>
    </Card>

    {/* Pro Plan */}
    <Card className="relative">
      <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground">
        Most Popular
      </div>
      <CardHeader>
        <CardTitle>Pro</CardTitle>
        <CardDescription>For small teams</CardDescription>
        <div className="mt-4">
          <span className="text-4xl font-bold">$29</span>
          <span className="text-muted-foreground">/month</span>
        </div>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2 text-sm">
          <li className="flex items-center">
            <Check className="mr-2 h-4 w-4 text-primary" />
            10 projects
          </li>
          <li className="flex items-center">
            <Check className="mr-2 h-4 w-4 text-primary" />
            All features
          </li>
          <li className="flex items-center">
            <Check className="mr-2 h-4 w-4 text-primary" />
            Priority support
          </li>
        </ul>
      </CardContent>
      <CardFooter>
        <Button className="w-full">Get Started</Button>
      </CardFooter>
    </Card>

    {/* Enterprise Plan */}
    <Card>
      <CardHeader>
        <CardTitle>Enterprise</CardTitle>
        <CardDescription>For large organizations</CardDescription>
        <div className="mt-4">
          <span className="text-4xl font-bold">$99</span>
          <span className="text-muted-foreground">/month</span>
        </div>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2 text-sm">
          <li className="flex items-center">
            <Check className="mr-2 h-4 w-4 text-primary" />
            Unlimited projects
          </li>
          <li className="flex items-center">
            <Check className="mr-2 h-4 w-4 text-primary" />
            Custom features
          </li>
          <li className="flex items-center">
            <Check className="mr-2 h-4 w-4 text-primary" />
            Dedicated support
          </li>
        </ul>
      </CardContent>
      <CardFooter>
        <Button className="w-full" variant="outline">Contact Sales</Button>
      </CardFooter>
    </Card>
  </div>
</section>
```

## Modal/Dialog Examples

### Basic Dialog
```tsx
<Dialog>
  <DialogTrigger asChild>
    <Button variant="outline">Edit Profile</Button>
  </DialogTrigger>
  <DialogContent className="sm:max-w-[425px]">
    <DialogHeader>
      <DialogTitle>Edit profile</DialogTitle>
      <DialogDescription>
        Make changes to your profile here. Click save when you're done.
      </DialogDescription>
    </DialogHeader>
    <div className="grid gap-4 py-4">
      <div className="grid grid-cols-4 items-center gap-4">
        <Label htmlFor="name" className="text-right">Name</Label>
        <Input id="name" value="Pedro Duarte" className="col-span-3" />
      </div>
      <div className="grid grid-cols-4 items-center gap-4">
        <Label htmlFor="username" className="text-right">Username</Label>
        <Input id="username" value="@peduarte" className="col-span-3" />
      </div>
    </div>
    <DialogFooter>
      <Button type="submit">Save changes</Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

### Alert Dialog
```tsx
<AlertDialog>
  <AlertDialogTrigger asChild>
    <Button variant="destructive">Delete Account</Button>
  </AlertDialogTrigger>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
      <AlertDialogDescription>
        This action cannot be undone. This will permanently delete your account
        and remove your data from our servers.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Cancel</AlertDialogCancel>
      <AlertDialogAction>Continue</AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

## Django Template Layout

### base.html
```html
{% load static %}
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}My App{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'css/styles.css' %}">
</head>
<body class="min-h-screen bg-background font-sans antialiased">
  <div class="relative flex min-h-screen flex-col">
    {% include "components/header.html" %}
    <main class="flex-1">
      {% block content %}{% endblock %}
    </main>
    {% include "components/footer.html" %}
  </div>
</body>
</html>
```

### components/header.html
```html
<header class="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
  <div class="container flex h-14 items-center">
    <div class="mr-4 hidden md:flex">
      <a href="/" class="mr-6 flex items-center space-x-2">
        <svg class="h-6 w-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        <span class="hidden font-bold sm:inline-block">My App</span>
      </a>
      <nav class="flex items-center space-x-6 text-sm font-medium">
        <a href="/features" class="transition-colors hover:text-foreground/80 text-foreground/60">Features</a>
        <a href="/pricing" class="transition-colors hover:text-foreground/80 text-foreground/60">Pricing</a>
        <a href="/docs" class="transition-colors hover:text-foreground/80 text-foreground/60">Docs</a>
      </nav>
    </div>
    <div class="flex flex-1 items-center justify-between space-x-2 md:justify-end">
      <nav class="flex items-center gap-2">
        <button class="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 hover:bg-accent hover:text-accent-foreground h-9 w-9">
          <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
          </svg>
        </button>
        <a href="/login" class="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2">
          Login
        </a>
      </nav>
    </div>
  </div>
</header>
```

### components/footer.html
```html
<footer class="border-t py-6 md:py-0">
  <div class="container flex flex-col items-center justify-center gap-4 md:h-24 md:flex-row">
    <p class="text-center text-sm leading-loose text-muted-foreground md:text-left">
      Built with Tailwind CSS. The source code is available on
      <a href="https://github.com" class="font-medium underline underline-offset-4">GitHub</a>.
    </p>
  </div>
</footer>
```

## Responsive Patterns

### Container
```tsx
// Basic container
<div className="container mx-auto px-4">
  {/* Content */}
</div>

// Container with max width
<div className="container mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
  {/* Content */}
</div>
```

### Grid System
```tsx
// 2 columns on mobile, 3 on tablet, 4 on desktop
<div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
  {/* Grid items */}
</div>

// Span multiple columns
<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
  <div className="md:col-span-2">
    {/* Takes 2 columns */}
  </div>
  <div>
    {/* Takes 1 column */}
  </div>
</div>
```

### Flexbox
```tsx
// Center content
<div className="flex items-center justify-center min-h-screen">
  {/* Centered content */}
</div>

// Space between items
<div className="flex items-center justify-between">
  <span>Left</span>
  <span>Right</span>
</div>

// Wrap items
<div className="flex flex-wrap gap-4">
  {/* Wrapped items */}
</div>
```

## Animation Examples

### Hover Effects
```tsx
// Scale on hover
<Button className="transition-transform hover:scale-105">
  Hover me
</Button>

// Shadow on hover
<Card className="transition-shadow hover:shadow-lg">
  {/* Card content */}
</Card>

// Color transition
<div className="transition-colors hover:bg-primary hover:text-primary-foreground">
  {/* Content */}
</div>
```

### Loading States
```tsx
// Spinner
<Button disabled>
  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
  Please wait
</Button>

// Skeleton loading
<div className="space-y-2">
  <Skeleton className="h-4 w-[250px]" />
  <Skeleton className="h-4 w-[200px]" />
</div>
```

### Transitions
```tsx
// Fade in
<div className="animate-in fade-in duration-500">
  {/* Content */}
</div>

// Slide in
<div className="animate-in slide-in-from-bottom-4 duration-500">
  {/* Content */}
</div>
```
