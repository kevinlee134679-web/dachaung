export type RangeQuery = Record<string, string | number | boolean | bigint | null | undefined>

export function rangeQuery(query: RangeQuery): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== null && value !== undefined) params.append(key, String(value))
  }
  return params.toString()
}
