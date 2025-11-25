from typing import Tuple

class UniversalValidator:
    """
    Acts as the quality gatekeeper.
    - Logic and heuristic checks (e.g., empty responses, refusal).
    """

    @staticmethod
    def validate(content: str) -> Tuple[bool, str]:
        if not content.strip():
            return False, "Error: Empty output generated."

        # Simple heuristic: Reject short, evasive, or broken outputs
        if len(content) < 5:
            return False, "Error: Response too short to be valid."
        if "I cannot" in content or "I am an AI" in content:
            # Soft warning, but we flag it to ensure it was intentional
            return True, "Warning: Potential refusal detected."
        return True, "Logic Valid"