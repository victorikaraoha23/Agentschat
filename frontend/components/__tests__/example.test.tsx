import { Button } from "@/components/ui/button"
import { renderWithProviders } from "@/test/utils"
import { describe, expect, it } from "vitest"

describe("example", () => {
  it("renders a button with text", () => {
    const { getByRole } = renderWithProviders(<Button>Click me</Button>)
    expect(getByRole("button", { name: "Click me" })).toBeInTheDocument()
  })
})
