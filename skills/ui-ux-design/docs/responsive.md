# Responsive Design Reference

## Breakpoints

```css
/* Mobile-first breakpoints */
/* sm: 640px   - Large phones */
/* md: 768px   - Tablets */
/* lg: 1024px  - Small laptops */
/* xl: 1280px  - Desktops */
/* 2xl: 1536px - Large screens */

@media (min-width: 640px) { /* sm */ }
@media (min-width: 768px) { /* md */ }
@media (min-width: 1024px) { /* lg */ }
@media (min-width: 1280px) { /* xl */ }
@media (min-width: 1536px) { /* 2xl */ }
```

## CSS Grid Layouts

```css
/* Auto-fit responsive grid */
.grid-auto {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1rem;
}

/* Named grid areas */
.layout {
  display: grid;
  grid-template-areas:
    "header"
    "main"
    "sidebar"
    "footer";
  grid-template-rows: auto 1fr auto;
}

@media (min-width: 768px) {
  .layout {
    grid-template-areas:
      "header header"
      "sidebar main"
      "footer footer";
    grid-template-columns: 250px 1fr;
  }
}

/* Dashboard grid */
.dashboard {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 1.5rem;
}
```

## Flexbox Patterns

```css
/* Centering */
.center {
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Space between */
.between {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* Wrap with gap */
.wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}

/* Sticky footer */
.page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.page__content {
  flex: 1;
}

/* Holy grail layout */
.holy-grail {
  display: flex;
  min-height: 100vh;
}

.holy-grail__nav { width: 250px; }
.holy-grail__content { flex: 1; }
.holy-grail__aside { width: 300px; }

@media (max-width: 768px) {
  .holy-grail {
    flex-direction: column;
  }
  .holy-grail__nav,
  .holy-grail__aside {
    width: 100%;
  }
}
```

## Fluid Typography

```css
/* clamp() for fluid sizing */
h1 {
  font-size: clamp(1.5rem, 4vw + 1rem, 3rem);
}

h2 {
  font-size: clamp(1.25rem, 3vw + 0.5rem, 2rem);
}

body {
  font-size: clamp(1rem, 0.5vw + 0.875rem, 1.125rem);
  line-height: 1.6;
}

/* Fluid spacing */
.section {
  padding: clamp(1rem, 5vw, 4rem);
}
```

## Container Queries

```css
.card-container {
  container-type: inline-size;
  container-name: card;
}

.card {
  display: flex;
  flex-direction: column;
}

@container card (min-width: 400px) {
  .card {
    flex-direction: row;
  }
}

@container card (min-width: 600px) {
  .card__title {
    font-size: 1.5rem;
  }
}
```

## Responsive Images

```html
<!-- Responsive image with art direction -->
<picture>
  <source media="(min-width: 1024px)" srcset="large.jpg">
  <source media="(min-width: 640px)" srcset="medium.jpg">
  <img src="small.jpg" alt="Description" loading="lazy" decoding="async">
</picture>

<!-- Responsive image with density -->
<img
  srcset="logo.png 1x, logo-2x.png 2x"
  src="logo.png"
  alt="Logo"
  width="200"
  height="100"
>

<!-- Lazy loading -->
<img src="photo.jpg" alt="Description" loading="lazy" decoding="async">
```

## Touch Targets

```css
/* Minimum 44x44px touch targets */
.button,
.link,
.touch-target {
  min-height: 44px;
  min-width: 44px;
  padding: 12px 16px;
}

/* Larger touch areas for mobile */
@media (pointer: coarse) {
  button, a, input, select, textarea {
    min-height: 44px;
  }
}
```

## Mobile-First Patterns

```css
/* Mobile: single column */
.container {
  padding: 1rem;
}

/* Tablet: wider */
@media (min-width: 768px) {
  .container {
    padding: 2rem;
    max-width: 720px;
    margin: 0 auto;
  }
}

/* Desktop: max width */
@media (min-width: 1024px) {
  .container {
    max-width: 960px;
  }
}

/* Wide: full layout */
@media (min-width: 1280px) {
  .container {
    max-width: 1200px;
  }
}
```
