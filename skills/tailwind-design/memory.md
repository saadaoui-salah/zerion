# Tailwind Design Skill Memory

## Key Learnings

### Component Patterns
- Always use semantic HTML elements
- Implement proper focus states with focus-visible:
- Use CSS variables for theming
- Support dark mode with dark: variants
- Use class-variance-authority for component variants

### Responsive Design
- Mobile-first approach: Design for mobile, enhance for larger screens
- Use container queries when appropriate
- Implement fluid typography with clamp()
- Create responsive grid layouts

### Performance
- Use Tailwind's purge feature to remove unused classes
- Implement lazy loading for images
- Use CSS containment for complex components
- Minimize re-renders with proper React patterns

### Accessibility
- Ensure proper color contrast (WCAG AA minimum)
- Use focus-visible: rings for keyboard navigation
- Implement proper ARIA labels and roles
- Support screen readers with semantic HTML

## Framework-Specific Notes

### Django
- Use {% tailwind_css %} template tag in base templates
- Implement django-tailwind for automatic CSS compilation
- Create reusable template components with {% include %}
- Use Django forms with Tailwind-styled inputs

### React
- Create reusable component libraries with proper TypeScript types
- Use className composition with clsx or twMerge
- Implement component variants using cva
- Build accessible components with proper ARIA attributes

### Next.js
- Leverage Next.js Image component with Tailwind styling
- Implement server components with Tailwind classes
- Use next/font for optimized font loading
- Create layout components for consistent page structure

## Common Patterns

### Card Component
```tsx
<div className="rounded-lg border bg-card text-card-foreground shadow-sm">
  <div className="flex flex-col space-y-1.5 p-6">
    <h3 className="text-2xl font-semibold leading-none tracking-tight">Title</h3>
    <p className="text-sm text-muted-foreground">Description</p>
  </div>
  <div className="p-6 pt-0">
    {/* Content */}
  </div>
</div>
```

### Button Component
```tsx
<button className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2">
  Button
</button>
```

### Input Component
```tsx
<input className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50" />
```

## Troubleshooting

### Common Issues
1. **Styles not applying**: Check if Tailwind is in your content paths
2. **Dark mode not working**: Add darkMode: ["class"] to tailwind.config.js
3. **Build errors**: Clear node_modules and reinstall
4. **Django static files not found**: Run python manage.py collectstatic

### Solutions
1. Verify tailwind.config.js content paths
2. Add class="dark" to HTML element
3. Check for conflicting PostCSS plugins
4. Verify TAILWIND_CSS_PATH setting

## Best Practices

### Do's
- Use semantic HTML elements
- Implement proper focus states
- Support dark mode
- Test across browsers and devices
- Document component usage

### Don'ts
- Don't use inline styles
- Don't ignore accessibility
- Don't skip responsive design
- Don't forget to test dark mode
- Don't use !important

## Resources

- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [shadcn/ui Components](https://ui.shadcn.com/)
- [Radix UI Primitives](https://www.radix-ui.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [Django Documentation](https://docs.djangoproject.com/)
