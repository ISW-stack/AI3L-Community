import DOMPurify from 'dompurify'

export function stripHtml(html: string): string {
  return html.replace(/<[^>]*>/g, '')
}

/**
 * Check whether HTML content from TiptapEditor is effectively empty.
 * Handles `<p></p>`, `<p><br></p>`, whitespace-only text, etc.
 * Returns false for media tags (img, video, table, etc.) even with no text.
 */
export function isContentEmpty(html: string): boolean {
  if (!html || html === '<p></p>') return true
  if (/<(img|iframe|video|audio|embed|object|source|table)\b/i.test(html)) return false
  return !html.replace(/<[^>]*>/g, '').trim()
}

/**
 * Replace @username patterns in HTML content with styled mention spans.
 * Only usernames listed in the mentions array are highlighted.
 */
const UUID_RE = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'

/**
 * Extract SIG URLs (/sigs/<uuid>) from HTML content.
 * Returns deduplicated list of { fullMatch, id } objects.
 */
export function extractSigUrls(html: string): { fullMatch: string; id: string }[] {
  const pattern = new RegExp(`/sigs/(${UUID_RE})(?![/\\w])`, 'gi')
  const seen = new Set<string>()
  const results: { fullMatch: string; id: string }[] = []
  let match: RegExpExecArray | null
  while ((match = pattern.exec(html)) !== null) {
    const id = match[1].toLowerCase()
    if (!seen.has(id)) {
      seen.add(id)
      results.push({ fullMatch: match[0], id })
    }
  }
  return results
}

/**
 * Extract Form URLs (/forms/<uuid>) from HTML content.
 * Skips /edit and /export suffixes.
 * Returns deduplicated list of { fullMatch, id } objects.
 */
export function extractFormUrls(html: string): { fullMatch: string; id: string }[] {
  const pattern = new RegExp(`/forms/(${UUID_RE})(?!/edit|/export)(?![/\\w])`, 'gi')
  const seen = new Set<string>()
  const results: { fullMatch: string; id: string }[] = []
  let match: RegExpExecArray | null
  while ((match = pattern.exec(html)) !== null) {
    const id = match[1].toLowerCase()
    if (!seen.has(id)) {
      seen.add(id)
      results.push({ fullMatch: match[0], id })
    }
  }
  return results
}

export function extractMentions(text: string): string[] {
  const seen = new Set<string>()
  const pattern = /@([\w-]+)/g
  let match: RegExpExecArray | null
  while ((match = pattern.exec(text)) !== null) {
    seen.add(match[1])
  }
  return Array.from(seen)
}

export function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/**
 * Validate that a URL uses http: or https: protocol.
 * Rejects javascript:, data:, and other potentially dangerous schemes.
 */
export function isValidUrl(url: string): boolean {
  try {
    const parsed = new URL(url, window.location.origin)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

export function renderMentions(html: string, mentions: string[] | null): string {
  if (!mentions || mentions.length === 0) return html

  // SSR / test environments without a DOM: fall back to regex on raw HTML string
  if (typeof document === 'undefined') {
    let result = html
    for (const username of mentions) {
      const escaped = username.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      const pattern = new RegExp(`@${escaped}(?![\\w-])`, 'g')
      result = result.replace(
        pattern,
        `<span class="text-brand-600 font-semibold">@${escapeHtml(username)}</span>`,
      )
    }
    return result
  }

  // Build a combined pattern to match any listed mention in text nodes only
  const escapedNames = mentions.map((u) => u.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const combinedPattern = new RegExp(`@(${escapedNames.join('|')})(?![\\w-])`, 'g')

  const container = document.createElement('div')
  container.innerHTML = html

  function walkTextNodes(node: Node): void {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = node.textContent ?? ''
      if (!combinedPattern.test(text)) return
      combinedPattern.lastIndex = 0

      const frag = document.createDocumentFragment()
      let lastIndex = 0
      let match: RegExpExecArray | null

      while ((match = combinedPattern.exec(text)) !== null) {
        if (match.index > lastIndex) {
          frag.appendChild(document.createTextNode(text.slice(lastIndex, match.index)))
        }
        const span = document.createElement('span')
        span.className = 'text-brand-600 font-semibold'
        span.textContent = `@${match[1]}`
        frag.appendChild(span)
        lastIndex = match.index + match[0].length
      }

      if (lastIndex < text.length) {
        frag.appendChild(document.createTextNode(text.slice(lastIndex)))
      }

      node.parentNode?.replaceChild(frag, node)
      return
    }

    // Walk child nodes (clone list to avoid mutation during iteration)
    const children = Array.from(node.childNodes)
    for (const child of children) {
      walkTextNodes(child)
    }
  }

  walkTextNodes(container)
  // Re-sanitize after DOM re-serialization to prevent mXSS
  return DOMPurify.sanitize(container.innerHTML)
}
