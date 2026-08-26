export function truncateAtSentenceBoundary(
  value: unknown,
  maxChars = 220,
): string {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  if (text.length <= maxChars) return text;

  const windowText = text.slice(0, maxChars).trimEnd();
  let end = Math.max(
    windowText.lastIndexOf("."),
    windowText.lastIndexOf("?"),
    windowText.lastIndexOf("!"),
  );

  if (end < Math.max(60, Math.floor(maxChars / 3))) {
    end = windowText.lastIndexOf(";");
  }

  if (end < Math.max(60, Math.floor(maxChars / 3))) {
    end = windowText.lastIndexOf(" ");
  }

  const summary =
    end > 0
      ? windowText.slice(0, end + 1).replace(/[ ,;:]+$/, "")
      : windowText.replace(/[ ,;:]+$/, "");

  return `${summary}...`;
}
