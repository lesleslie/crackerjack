// Minimal web fixture TypeScript module: clean, type-safe, no ESLint violations.

export function greet(name: string): string {
  return `Hello, ${name}!`;
}

if (typeof window !== "undefined") {
  const target = document.getElementById("app");
  if (target) {
    target.textContent = greet("World");
  }
}
