export function copyValue<T>(value: T): T {
  return structuredClone(value)
}
