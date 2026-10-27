/**
 * Models sometimes answer with light markdown. The chat shows plain text, so emphasis markers and
 * backticks are removed and "* " bullets become "• ".
 */
export function plainText(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/gs, '$1')
    .replace(/__(.+?)__/gs, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^[ \t]*[*-] /gm, '• ')
    .replace(/^#{1,6} /gm, '')
    .trim();
}
