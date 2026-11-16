/**
 * Prefix a root-relative public asset path with the configured basePath.
 * next/link and next/image already honor basePath; use this for raw <img>,
 * fetch(), or CSS url() values that bypass those helpers.
 */
export function withBasePath(path: string): string {
  const base = process.env.NEXT_PUBLIC_BASE_PATH?.replace(/\/$/, "") ?? "";
  if (!path.startsWith("/")) {
    return `${base}/${path}`;
  }
  return `${base}${path}`;
}
