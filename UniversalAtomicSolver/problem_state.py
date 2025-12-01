from dataclasses import dataclass
from typing import Optional

@dataclass
class ProblemState:
    """
    Represents the strict snapshot of reality.
    The AI does NOT see a chat history. It only sees this object.
    """
    solution_content: str = ""  # The accumulator for code or text response
    context: str = ""  # File system context or background info
    last_error: Optional[str] = None  # validation errors

    def get_prompt_context(self) -> str:
        """Serializes the state for the LLM. No chat history included."""
        return f"""
        --- CURRENT ATOMIC STATE ---
        [EXISTING SOLUTION CONTENT]:
        {self.solution_content if self.solution_content else "(Empty)"}

        [CONTEXT / ENVIRONMENT]:
        {self.context}

        [LAST VALIDATION ERROR]:
        {self.last_error if self.last_error else "None"}
        ----------------------------
        """