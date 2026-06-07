# Accessibility Reference

## WCAG 2.1 Quick Reference

### Perceivable
- **1.1.1** Text alternatives for non-text content
- **1.3.1** Info and relationships (semantic HTML)
- **1.4.1** Use of color (not sole indicator)
- **1.4.3** Contrast minimum (4.5:1 normal, 3:1 large)
- **1.4.4** Resize text (up to 200%)
- **1.4.10** Reflow (no horizontal scroll at 320px)
- **1.4.11** Non-text contrast (3:1 UI components)
- **1.4.12** Text spacing (adjustable)

### Operable
- **2.1.1** Keyboard accessible
- **2.1.2** No keyboard trap
- **2.4.1** Bypass blocks (skip links)
- **2.4.3** Focus order
- **2.4.6** Headings and labels
- **2.4.7** Focus visible
- **2.5.3** Label in name
- **2.5.4** Motion actuation

### Understandable
- **3.1.1** Language of page
- **3.2.1** On focus
- **3.2.2** On input
- **3.3.1** Error identification
- **3.3.2** Labels or instructions
- **3.3.3** Error suggestion
- **3.3.4** Error prevention

### Robust
- **4.1.1** Parsing
- **4.1.2** Name, role, value
- **4.1.3** Status messages

## Semantic HTML

```html
<!-- Landmarks -->
<header role="banner">...</header>
<nav aria-label="Main">...</nav>
<main role="main">...</main>
<aside aria-label="Related">...</aside>
<footer role="contentinfo">...</footer>

<!-- Headings (logical order) -->
<h1>Page Title</h1>
  <h2>Section</h2>
    <h3>Subsection</h3>

<!-- Lists -->
<ul> <!-- Unordered -->
<ol> <!-- Ordered -->
<dl> <!-- Definition -->

<!-- Tables -->
<table>
  <caption>Quarterly Results</caption>
  <thead>
    <tr><th scope="col">Q1</th></tr>
  </thead>
  <tbody>
    <tr><td>Value</td></tr>
  </tbody>
</table>

<!-- Forms -->
<form>
  <label for="email">Email</label>
  <input id="email" type="email" required aria-describedby="email-help">
  <span id="email-help">We'll never share your email</span>

  <fieldset>
    <legend>Choose one</legend>
    <input type="radio" id="opt1" name="choice" value="1">
    <label for="opt1">Option 1</label>
  </fieldset>
</form>
```

## ARIA Patterns

```html
<!-- Live region for dynamic updates -->
<div aria-live="polite" aria-atomic="true">
  3 items in cart
</div>

<!-- Loading state -->
<button aria-busy="true">
  <span class="sr-only">Loading...</span>
</button>

<!-- Expanded/collapsed -->
<button aria-expanded="false" aria-controls="menu-1">
  Menu
</button>
<ul id="menu-1" role="menu" hidden>
  <li role="menuitem">Item 1</li>
</ul>

<!-- Modal dialog -->
<dialog aria-labelledby="dialog-title" aria-modal="true">
  <h2 id="dialog-title">Confirm</h2>
</dialog>

<!-- Tab panel -->
<div role="tablist" aria-label="Settings">
  <button role="tab" aria-selected="true" aria-controls="panel-1" id="tab-1">
    General
  </button>
  <button role="tab" aria-selected="false" aria-controls="panel-2" id="tab-2" tabindex="-1">
    Advanced
  </button>
</div>
<div role="tabpanel" id="panel-1" aria-labelledby="tab-1">
  Content
</div>

<!-- Alert -->
<div role="alert" aria-live="assertive">
  Error: Invalid email address
</div>

<!-- Progress -->
<progress aria-label="Upload progress" value="70" max="100">70%</progress>
```

## Keyboard Navigation

```css
/* Focus visible indicator */
:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}

/* Skip link */
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  background: #2563eb;
  color: white;
  padding: 8px;
  z-index: 100;
}

.skip-link:focus {
  top: 0;
}
```

```html
<a href="#main" class="skip-link">Skip to main content</a>
<main id="main" tabindex="-1">
  <!-- Content -->
</main>
```

## Screen Reader Text

```css
/* Visually hidden but accessible */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* Visible on focus only */
.sr-only-focusable:focus {
  position: static;
  width: auto;
  height: auto;
  padding: inherit;
  margin: inherit;
  overflow: visible;
  clip: auto;
  white-space: normal;
}
```

## Color Contrast Checker

```js
// Contrast ratio calculation
function getLuminance(r, g, b) {
  const [rs, gs, bs] = [r, g, b].map(c => {
    c /= 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

function getContrastRatio(color1, color2) {
  const l1 = getLuminance(...color1);
  const l2 = getLuminance(...color2);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

// WCAG AA requires 4.5:1 for normal text, 3:1 for large text
```
