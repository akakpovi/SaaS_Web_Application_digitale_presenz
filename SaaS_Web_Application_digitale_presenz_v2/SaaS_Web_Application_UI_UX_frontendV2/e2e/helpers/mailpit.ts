/**
 * Mailpit helpers.
 *
 * The local stack delivers every e-mail to Mailpit instead of the internet
 * (SMTP on 1025, HTTP API on 8025). Tests read the real message the backend
 * sent — the verification link is never fabricated.
 */

const MAILPIT_URL = process.env.MAILPIT_URL ?? "http://localhost:8025"

export interface MailpitMessage {
  ID: string
  To: { Address: string }[]
  Subject: string
  Created: string
}

interface MailpitListResponse {
  messages: MailpitMessage[]
}

async function listMessages(): Promise<MailpitMessage[]> {
  const response = await fetch(`${MAILPIT_URL}/api/v1/messages?limit=50`)
  if (!response.ok) {
    throw new Error(`Mailpit answered ${response.status} on ${MAILPIT_URL}`)
  }
  const payload = (await response.json()) as MailpitListResponse
  return payload.messages ?? []
}

/** Waits until at least one message was delivered to `recipient`. */
export async function waitForMessage(
  recipient: string,
  timeoutMs = 20_000,
): Promise<MailpitMessage> {
  const deadline = Date.now() + timeoutMs
  const target = recipient.toLowerCase()

  while (Date.now() < deadline) {
    const messages = await listMessages()
    const matching = messages
      .filter((message) =>
        message.To?.some((to) => to.Address.toLowerCase() === target),
      )
      .sort(
        (a, b) => new Date(b.Created).getTime() - new Date(a.Created).getTime(),
      )
    if (matching.length > 0) return matching[0]
    await new Promise((resolve) => setTimeout(resolve, 500))
  }

  throw new Error(`No e-mail delivered to ${recipient} within ${timeoutMs} ms`)
}

/** Returns the plain-text (or HTML) body of a message. */
export async function messageBody(messageId: string): Promise<string> {
  const response = await fetch(`${MAILPIT_URL}/api/v1/message/${messageId}`)
  if (!response.ok) {
    throw new Error(`Mailpit answered ${response.status} for message ${messageId}`)
  }
  const payload = (await response.json()) as { Text?: string; HTML?: string }
  return payload.Text || payload.HTML || ""
}

/**
 * Extracts a path from a link in the e-mail body, e.g.
 * `https://localhost/verify-email?uid=…&token=…` → `/verify-email?uid=…&token=…`.
 */
export function extractPath(body: string, prefix: string): string {
  const pattern = new RegExp(`${prefix.replace(/[/?]/g, "\\$&")}\\?[^\\s"<>]+`)
  const match = body.match(pattern)
  if (!match) {
    throw new Error(`No ${prefix} link found in the e-mail body`)
  }
  // The body is plain text: strip a trailing newline/CR and HTML entity noise.
  return match[0].replace(/&amp;/g, "&").replace(/[\r\n]+$/, "")
}
