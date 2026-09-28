"""Per-request context visible to tools (same ContextVar idea as request_id).

Tools must be able to check what the *user* actually said, independently of
what the model claims, e.g. "did the user ask me to remember this?"
"""
from contextvars import ContextVar

user_message_var: ContextVar[str] = ContextVar("user_message", default="")
