from __future__ import annotations
from typing import Literal, TypedDict, overload

# Rich imports
from rich import print as rprint
from rich.text import Text

class MessageEntry(TypedDict):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: str | None # Optional, only for role 'tool'
    name: str | None # Optional, only for role 'tool'
    # For assistant messages that include tool_calls
    tool_calls: list[dict] | None # Optional, only for role 'assistant' if it requests tool calls

class InteractionHistory:
    def __init__(self):
        self._history: list[MessageEntry] = []

    @overload
    def add_entry(self, role: Literal["system", "user", "assistant"], content: str, tool_calls: list[dict] | None = None) -> None:
        ...

    @overload
    def add_entry(self, role: Literal["tool"], content: str, tool_call_id: str, name: str) -> None:
        ...

    def add_entry(
        self, 
        role: Literal["system", "user", "assistant", "tool"], 
        content: str, 
        tool_call_id: str | None = None, 
        name: str | None = None,
        tool_calls: list[dict] | None = None
    ) -> None:
        """Adds an entry to the interaction history."""
        if not isinstance(role, str) or role not in ["system", "user", "assistant", "tool"]:
            raise ValueError("Role must be one of 'system', 'user', 'assistant', or 'tool'.")
        if not isinstance(content, str):
            # Allow empty content for certain roles like assistant (if it's just a tool call)
            if content is not None: # If it's explicitly None, we might allow it (e.g. for tool calls)
                 pass # Let LiteLLM handle None content for specific roles if it's valid.
            # else:
            # raise ValueError("Content must be a string.")

        entry: MessageEntry = {"role": role, "content": content}

        if role == "tool":
            if not tool_call_id or not isinstance(tool_call_id, str):
                raise ValueError("tool_call_id must be a non-empty string for role 'tool'.")
            if not name or not isinstance(name, str):
                raise ValueError("name must be a non-empty string for role 'tool'.")
            entry["tool_call_id"] = tool_call_id
            entry["name"] = name
        elif role == "assistant" and tool_calls:
            entry["tool_calls"] = tool_calls
        
        # Ensure None values for optional fields are not included if not provided
        # This helps with LiteLLM/OpenAI API compatibility.
        # However, the MessageEntry TypedDict defines them as optional, so they can be None.
        # LiteLLM's model_dump(exclude_none=True) handles this later.

        try:
            self._history.append(entry)
        except Exception as e:
            rprint(f"[bold red]Error adding to interaction history: {e}[/bold red]")

    def get_llm_history(self) -> list[MessageEntry]:
        """Returns the history formatted for LLM consumption."""
        # Directly return the history as it's already in the correct format
        return list(self._history) # Return a copy

    def clear_history(self) -> None:
        """Clears the interaction history."""
        self._history = []
        rprint(Text("Interaction history cleared.", style="dim yellow"))

    def add_raw_llm_message(self, message_dump: dict) -> None:
        """
        Adds a raw message dump (e.g., from response_message.model_dump()) to the history.
        This is useful for messages that include tool_calls.
        """
        # Basic validation, can be expanded
        if not isinstance(message_dump, dict) or "role" not in message_dump:
            raise ValueError("Invalid message dump provided. Must be a dict with at least a 'role'.")
        
        # Ensure content is a string if it exists and is None (OpenAI expects string or null)
        # LiteLLM handles this, but good to be mindful. If content is None, it's fine.
        # if message_dump.get("content") is None and "tool_calls" not in message_dump:
        #     message_dump["content"] = "" # Or handle as per API spec for None content

        # Cast to MessageEntry for type safety, though it's a structural check
        # This assumes message_dump conforms to MessageEntry structure.
        # More robust validation would involve checking all fields.
        self._history.append(message_dump) # type: ignore 