export function stripHtml(html: string): string {
  return html.replace(/<[^>]*>/g, '')
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

export function renderMentions(html: string, mentions: string[] | null): string {
  if (!mentions || mentions.length === 0) return html
  let result = html
  for (const username of mentions) {
    const escaped = username.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const pattern = new RegExp(`@${escaped}(?![\\w-])`, 'g')
    result = result.replace(
      pattern,
      `<span class="text-brand-600 font-semibold">@${username}</span>`,
    )
  }
  return result
}
