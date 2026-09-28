"""Rules for what JARVIS may remember. Enforced in code, not just in the prompt.

1. Explicit request ("remember that...", "don't forget...")  -> saved immediately.
2. Anything the model decides to remember on its own          -> a *proposal* that
   the user must approve in the UI. This matters for security: text JARVIS reads
   (a web page, an email) could say "remember that the user wants X". Without
   this rule, one poisoned document could plant a permanent instruction.
3. Secrets (passwords, card numbers, API keys...)              -> never stored.
"""
import re

from app.security.secrets import looks_secret  # noqa: F401  (re-exported)

_EXPLICIT_REMEMBER = re.compile(
    r"\b(remember|memori[sz]e|don'?t forget|do not forget|note (that|this|down)|"
    r"keep in mind|save (that|this))\b", re.IGNORECASE)
_EXPLICIT_FORGET = re.compile(
    r"\b(forget|delete|remove|erase)\b", re.IGNORECASE)



def user_asked_to_remember(user_message: str) -> bool:
    return bool(_EXPLICIT_REMEMBER.search(user_message))


def user_asked_to_forget(user_message: str) -> bool:
    return bool(_EXPLICIT_FORGET.search(user_message))
