"""Turn screen text into text that sounds right when spoken.

A reply like "It's **56°F** 🌧️ — see [radar](https://...)" looks fine on screen
but a TTS engine would read the asterisks, try to pronounce the emoji and the
URL. This runs before every synthesis.
"""
import re

_EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"  # pictographs, emoticons, transport, symbols...
    "☀-➿"          # misc symbols & dingbats (☀ ☔ ✈ ✅ ...)
    "⬀-⯿"          # arrows, stars
    "️‍"           # emoji variation selector / zero-width joiner
    "]+"
)

_REPLACEMENTS = [
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),       # [text](url) -> text
    (re.compile(r"https?://\S+"), "the link"),             # bare URLs
    (re.compile(r"```.*?```", re.DOTALL), " "),            # code blocks: don't read code aloud
    (re.compile(r"[*_`#>]+"), ""),                          # markdown symbols
    (re.compile(r"^\s*[-+]\s+", re.MULTILINE), ""),         # list bullets
    (re.compile(r"°\s?[FC]\b"), " degrees"),                # 56°F -> 56 degrees
    (re.compile(r"°"), " degrees"),
    (re.compile(r"(\d)\s?%"), r"\1 percent"),
    (re.compile(r"\bkm/h\b"), "kilometers per hour"),
    (re.compile(r"\bmph\b"), "miles per hour"),
    (re.compile(r"\s*[—–]\s*"), ", "),                      # dashes -> a short pause
]


def to_speakable(text: str) -> str:
    text = _EMOJI.sub("", text)
    for pattern, replacement in _REPLACEMENTS:
        text = pattern.sub(replacement, text)
    # Line breaks become sentence pauses, unless the line already ended in
    # punctuation (e.g. "Conditions:\n- Drizzle" -> "Conditions: Drizzle").
    text = re.sub(r"(?<=[.!?:;,])\s*\n+\s*", " ", text.strip())
    text = re.sub(r"\s*\n+\s*", ". ", text)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)  # "cloudy ." -> "cloudy."
    return re.sub(r"\s{2,}", " ", text).strip()
