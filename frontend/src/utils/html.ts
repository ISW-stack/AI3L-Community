export function stripHtml(html: string): string {
  return html.replace(/<[^>]*>/g, '')
}

/**
 * Replace @username patterns in HTML content with styled mention spans.
 * Only usernames listed in the mentions array are highlighted.
 */
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
