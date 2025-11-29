from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Optional


class BruteAgent:
    """Agent responsible for generating brute force solutions."""

    def __init__(self, model_name: str):
        self.model = self._create_model(model_name, temperature=0.6)
        self.system_prompt = """You are a brute force algorithm expert.

Your task is to generate a SIMPLE, CORRECT brute force solution in Python.

Guidelines:
- Prioritize CORRECTNESS over efficiency
- Use simple, straightforward approaches (nested loops, recursion, etc.)
- Don't worry about time/space complexity
- Read input from stdin, write output to stdout
- Handle the exact input/output format specified
- Include proper input parsing
- No unnecessary comments or explanations in code
- Make sure the solution is complete and runnable
- Carefully handle 1-indexed inputs—allocate arrays/lists with length N+1 (or larger) if any and guard every index access to avoid out-of-range errors

Output ONLY the Python code, no markdown, no explanations.
ABSOLUTELY NO EXPLANATIONS OR MARKDOWN.
OUTPUT RAW PYTHON CODE ONLY.
"""

    def generate_solution(self, problem_statement: str, temperature: float = 0.3,
                          feedback: Optional[str] = None, attempt: int = 1) -> str:
        """Generate brute force solution for the given problem."""
        user_message = (
            "REMINDER: Respond with ONLY raw Python code. No explanations, no markdown.\n\n"
            f"Generate a brute force Python solution for this problem:\n\n{problem_statement}"
        )

        if feedback:
            user_message += (
                f"\n\n=== FEEDBACK FROM ATTEMPT {attempt - 1} ===\n"
                f"{feedback}\n\nPlease fix the issues and generate a corrected brute force solution."
            )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message}
        ]

        response = self.model.invoke(messages, temperature=temperature)
        code = response.content.strip()

        # Remove markdown code blocks if present
        if code.startswith("```python"):
            code = code.split("```python")[1].split("```")[0].strip()
        elif code.startswith("```"):
            code = code.split("```")[1].split("```")[0].strip()

        return code

    @staticmethod
    def _create_model(model_name: str, **kwargs):
        model = model_name
        if ":" in model_name:
            provider, model = model_name.split(":", 1)
        else:
            provider = "openai"
        if model.startswith("models/"):
            model = model.replace("models/", "")
        provider = provider.lower()
        if provider == "google":
            return ChatGoogleGenerativeAI(model=model, **kwargs)
        if provider == "openai":
            return ChatOpenAI(model=model, **kwargs)
        raise ValueError(f"Unsupported provider '{provider}'. Use google:* or openai:* models.")
