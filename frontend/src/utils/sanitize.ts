import DOMPurify, { type Config as DOMPurifyConfig } from 'dompurify'

/**
 * Centralized DOMPurify configuration for the AI3L Community app.
 * All HTML sanitization MUST use this config for consistency.
 */
export const SANITIZE_CONFIG: DOMPurifyConfig = {
  ALLOWED_TAGS: [
    'p',
    'br',
    'b',
    'i',
    'em',
    'strong',
    'u',
    's',
    'strike',
    'del',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'ul',
    'ol',
    'li',
    'blockquote',
    'pre',
    'code',
    'a',
    'img',
    'figure',
    'figcaption',
    'table',
    'thead',
    'tbody',
    'tr',
    'th',
    'td',
    'hr',
    'span',
    'div',
    'sup',
    'sub',
    'mark',
  ],
  ALLOWED_ATTR: [
    'href',
    'src',
    'alt',
    'title',
    'target',
    'class',
    'id',
    'width',
    'height',
    'colspan',
    'rowspan',
    'start',
    'type',
    'data-type',
    'data-mention',
    'data-id',
  ],
  ALLOW_DATA_ATTR: false,
  FORCE_BODY: true, // Prevents mXSS by forcing body context parsing
}

/** Sanitize HTML using the centralized config. */
export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, SANITIZE_CONFIG) as string
}

/**
 * Sanitize HTML for preview cards (strips images, links, attributes — basic formatting only).
 * Uses FORCE_BODY for mXSS prevention.
 */
export const PREVIEW_ALLOWED_TAGS = [
  'p',
  'br',
  'strong',
  'b',
  'em',
  'i',
  'ul',
  'ol',
  'li',
  'blockquote',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'code',
  'pre',
]

export function sanitizePreviewHtml(html: string): string {
  // Strip tables (and their content) before sanitizing to prevent cell text
  // from being flattened into garbled repeated text when tags are removed.
  const withoutTables = html.replace(/<table[\s>][\s\S]*?<\/table>/gi, '<p>[table]</p>')
  return DOMPurify.sanitize(withoutTables, {
    ALLOWED_TAGS: PREVIEW_ALLOWED_TAGS,
    ALLOWED_ATTR: [],
    FORCE_BODY: true,
  }) as string
}

/**
 * Add rel="noopener noreferrer" and target="_blank" to all external links.
 * Must be called AFTER sanitization (DOMPurify strips rel).
 */
export function addLinkSafety(html: string): string {
  if (typeof document === 'undefined') return html
  const container = document.createElement('div')
  container.innerHTML = html
  container.querySelectorAll('a[href]').forEach((a) => {
    const href = a.getAttribute('href') || ''
    // External links: starts with http:// or https:// and not same origin
    if (/^https?:\/\//i.test(href)) {
      a.setAttribute('rel', 'noopener noreferrer')
      a.setAttribute('target', '_blank')
    }
  })
  return container.innerHTML
}
