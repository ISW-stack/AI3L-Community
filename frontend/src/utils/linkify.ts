export interface TextSegment {
  text: string
  isUrl: boolean
}

const URL_REGEX =
  /https?:\/\/(?:[a-zA-Z0-9\-._~:/?#[\]@!$&'()*+,;=%]|(?:%[0-9A-Fa-f]{2}))+/g

export function linkify(text: string): TextSegment[] {
  const segments: TextSegment[] = []
  let lastIndex = 0

  for (const match of text.matchAll(URL_REGEX)) {
    const url = match[0]
    const start = match.index!

    if (start > lastIndex) {
      segments.push({ text: text.slice(lastIndex, start), isUrl: false })
    }

    // Strip trailing punctuation that's likely not part of the URL,
    // but keep closing parens if they have a matching open paren (Wikipedia-style URLs)
    let cleaned = url.replace(/[).,;:!?]+$/, '')
    const stripped = url.slice(cleaned.length)
    // Re-attach closing parens that have matching openers inside the URL
    if (stripped.startsWith(')')) {
      const opens = (cleaned.match(/\(/g) || []).length
      const closes = (cleaned.match(/\)/g) || []).length
      if (opens > closes) {
        cleaned += ')'
      }
    }
    segments.push({ text: cleaned, isUrl: true })

    const trailingLen = url.length - cleaned.length
    lastIndex = start + url.length

    if (trailingLen > 0) {
      segments.push({ text: url.slice(cleaned.length), isUrl: false })
    }
  }

  if (lastIndex < text.length) {
    segments.push({ text: text.slice(lastIndex), isUrl: false })
  }

  return segments.length > 0 ? segments : [{ text, isUrl: false }]
}
