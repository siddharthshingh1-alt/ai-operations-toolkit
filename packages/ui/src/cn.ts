/** Join class names, dropping falsy values. Keeps conditional classes readable. */
export function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}
