import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, type RenderOptions } from "@testing-library/react"
import type { ReactElement, ReactNode } from "react"

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
}

function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={makeClient()}>{children}</QueryClientProvider>
  )
}

export function renderWithProviders(
  ui: ReactElement,
  options?: Omit<RenderOptions, "wrapper">
) {
  return render(ui, { wrapper: Providers, ...options })
}

export * from "@testing-library/react"
