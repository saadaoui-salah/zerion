# UI/UX Design Setup

## Recommended Tools

### Design
- Figma (primary design tool)
- Adobe XD
- Sketch (macOS only)

### Development
- VS Code with extensions
- Chrome DevTools
- Storybook for component development

### Testing
- axe DevTools (accessibility)
- Lighthouse (performance, accessibility)
- WAVE (accessibility evaluation)
- Screen readers: NVDA (Windows), VoiceOver (macOS), TalkBack (Android)

## VS Code Extensions

```json
// Recommended extensions.json
{
  "recommendations": [
    "bradlc.vscode-tailwindcss",
    "dsznajder.es7-react-js-snippets",
    "esbenp.prettier-vscode",
    "stylelint.vscode-stylelint",
    "dbaeumer.vscode-eslint",
    "vue.volar",
    "svelte.svelte-vscode",
    "ms-vscode.vscode-typescript-next"
  ]
}
```

## Tailwind CSS Setup

```bash
# Install Tailwind CSS
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p

# Install additional plugins
npm install -D @tailwindcss/typography
npm install -D @tailwindcss/forms
npm install -D @tailwindcss/aspect-ratio
npm install -D clsx tailwind-merge
npm install -D class-variance-authority
```

### Tailwind Config

```js
// tailwind.config.js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-in-out',
        'slide-in': 'slideIn 0.3s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideIn: {
          '0%': { transform: 'translateY(-10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
    require('@tailwindcss/forms'),
  ],
};
```

### Utility Helper

```ts
// lib/utils.ts
import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

## CSS Architecture (BEM)

```css
/* Block */
.card { }

/* Element */
.card__header { }
.card__body { }
.card__footer { }

/* Modifier */
.card--featured { }
.card__header--compact { }

/* States */
.card__button--loading { }
.card__input--error { }
.card__link--active { }
```

## Animation Best Practices

```css
/* Respect user preferences */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}

/* Focus visible for keyboard users */
:focus-visible {
  outline: 2px solid var(--color-primary-500);
  outline-offset: 2px;
}

:focus:not(:focus-visible) {
  outline: none;
}

/* Smooth transitions */
.transition-all {
  transition-property: all;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  transition-duration: 150ms;
}

/* Hover lift effect */
.hover-lift {
  transition: transform 0.2s, box-shadow 0.2s;
}
.hover-lift:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}
```
