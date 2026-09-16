# RAG-Eval Frontend

Production-quality React frontend for the RAG-Eval evaluation platform.

## Tech Stack

- **React 18** with TypeScript
- **Vite** for build tooling
- **pnpm** package manager (v10.33.0)
- **React Router v6** for routing
- **TanStack Query v5** for server state
- **Radix UI** for accessible primitives
- **Tailwind CSS v3** for styling
- **Class Variance Authority (CVA)** for component variants
- **React Hook Form + Zod** for forms
- **Vitest + Testing Library** for testing
- **MSW** for API mocking

## Requirements

- Node.js 24 LTS (`cat .nvmrc`)
- pnpm 10.33.0 (via Corepack)

## Setup

```bash
# Enable corepack for pnpm
corepack enable

# Install dependencies
pnpm install --frozen-lockfile

# Copy environment file
cp .env.example .env
```

## Development

```bash
# Start dev server
pnpm dev

# Type checking
pnpm typecheck

# Linting
pnpm lint

# Formatting
pnpm format
pnpm format:check

# Testing
pnpm test
pnpm test:watch

# Full verification
pnpm check
```

## Build

```bash
# Production build
pnpm build

# Preview production build
pnpm preview
```

## Project Structure

```
frontend/
├── src/
│   ├── app/                    # Application-level code
│   │   ├── router.tsx          # Router configuration
│   │   ├── create-router.tsx   # Router factory
│   │   └── design-system/      # Design system showcase
│   ├── components/             # Reusable components
│   │   ├── ui/                 # UI primitives
│   │   └── layout/             # Layout components
│   ├── config/                 # Configuration
│   ├── hooks/                  # Custom React hooks
│   ├── lib/                    # Utilities and libraries
│   │   ├── api/                # API client
│   │   └── utils/              # Utility functions
│   ├── styles/                 # Global styles
│   ├── test/                   # Test utilities
│   └── main.tsx                # Entry point
├── public/                     # Static assets
├── index.html                  # HTML entry point
├── package.json
├── tsconfig.json               # TypeScript config
├── vite.config.ts              # Vite config
├── tailwind.config.js          # Tailwind config
├── eslint.config.js            # ESLint config
├── .prettierrc.json            # Prettier config
├── Dockerfile                  # Production Docker build
└── nginx.conf                  # Nginx configuration
```

## Component Library

Stage 1 provides 25+ reusable components:

### Form Controls
- `Button`, `IconButton`
- `Input`, `Textarea`
- `Select`, `Checkbox`, `Radio`, `Switch`

### Display
- `Badge`, `StatusBadge`
- `Table` (with TanStack Table integration)
- `Tabs`, `DropdownMenu`
- `Dialog`, `Tooltip`, `Popover`
- `ProgressBar`, `Spinner`, `Skeleton`

### Layout
- `Card`, `Surface`, `Panel`
- `EmptyState`, `Alert`
- `MetricCard`, `PageHeader`, `SectionHeader`

All components are built on Radix UI primitives for accessibility and support dark theme out of the box.

## Design System

The design system uses semantic CSS custom properties (design tokens) defined in `src/styles/index.css`:

### Colors
- **Background**: Near-black (#090A0D)
- **Surfaces**: Dark grays with elevation levels
- **Accent**: Cool blue-purple (~#6677FF)
- **Status**: Success, warning, error, info

### Typography
- **Font**: Inter (system UI fallback)
- **Scale**: xs (0.75rem) to 2xl (1.25rem)

### Aesthetic
"Engineering control panel" - dense, technical, restrained, dark.

Access the design system showcase at `/design-system` when running the dev server.

## API Integration

The API client is configured in `src/lib/api/client.ts`:

```typescript
import { apiRequest } from "@/lib/api/client";

// GET request
const data = await apiRequest<ResponseType>("/endpoint");

// POST request
const result = await apiRequest<ResponseType>("/endpoint", {
  method: "POST",
  body: { key: "value" },
});
```

Configure the API base URL in `.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Routing

React Router v6 is configured with a nested route structure:

```typescript
// src/app/create-router.tsx
const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "design-system", element: <DesignSystemShowcase /> },
    ],
  },
];
```

## State Management

TanStack Query v5 manages server state:

```typescript
import { useQuery, useMutation } from "@tanstack/react-query";

// Query
const { data, isLoading } = useQuery({
  queryKey: ["items"],
  queryFn: () => apiRequest<Item[]>("/items"),
});

// Mutation
const mutation = useMutation({
  mutationFn: (data) => apiRequest("/items", { method: "POST", body: data }),
});
```

## Testing

Vitest with Testing Library and MSW:

```typescript
import { render, screen } from "@testing-library/react";
import { Button } from "@/components/ui/button";

describe("Button", () => {
  it("renders correctly", () => {
    render(<Button>Click</Button>);
    expect(screen.getByRole("button")).toHaveTextContent("Click");
  });
});
```

## Docker

Production Docker build with multi-stage setup:

```bash
# Build image
docker build -t rag-eval-frontend .

# Run container
docker run -p 8080:80 rag-eval-frontend
```

The Dockerfile uses:
1. Node 24 Alpine for building
2. Nginx Alpine for serving static assets

## Path Aliases

TypeScript path aliases are configured:

```typescript
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";
```

## Code Quality

- **TypeScript**: Strict mode with `noUncheckedIndexedAccess`
- **ESLint**: Strict type-checked rules
- **Prettier**: 88-char line width, double quotes
- **Imports**: Type imports enforced

## Browser Support

- Modern browsers (Evergreen)
- ES2022+ features
- CSS custom properties

## License

Same as the parent RAG-Eval project.
