from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI


class TesterAgent:
    """Agent responsible for generating small test cases from problem statement."""

    def __init__(self, model_name: str):
        self.model = self._create_model(model_name, temperature=0.7)
        self.system_prompt = """You are a test case generation expert for programming problems.

TASK:
- Produce valid input for the given problem exactly as a competitive programming judge would read it.
- If the problem statement contains an official sample input, copy it verbatim at the beginning of your output.
- After the sample, add 3-4 additional SMALL custom test cases that explore edge scenarios.

FORMAT RULES:
- If the first line is the number of test cases T, ensure that line reflects the total number of cases (sample + custom).
- Never insert blank lines between test cases or inside any test case.
- Output plain numbers only; no explanations, no bullet points, no Markdown.
- Use small integers (≤ 50 where possible) and short arrays (length ≤ 6).

COVERAGE:
- Include cases such as: already non-decreasing array, strictly decreasing array, all equal elements, single-element array, and arrays requiring minimal vs. maximal change costs.
- Vary the cost patterns to stress different decisions (cheap prefix, expensive suffix, etc.).

CRITICAL: Output ONLY the final input stream, with the correct T and test cases in order.
"""

    def generate_test_cases(self, problem_statement: str) -> str:
        """Generate test cases for the given problem statement."""
        user_prompt = (
            "Generate the complete input stream adhering to the rules above.\n"
            "Steps:\n"
            "1. Detect whether the problem statement provides an Example Input; if so, copy it exactly.\n"
            "2. Append 8-10 additional custom test cases covering the mandated edge scenarios.\n"
            "3. Ensure the very first line (T) equals the total number of test cases you output.\n"
            "4. Use small values (≤ 50) and short arrays while respecting all constraints.\n"
            "5. Output plain text only—no commentary or blank lines anywhere.\n\n"
            f"Problem statement:\n\n{problem_statement}"
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = self.model.invoke(messages)
        content = response.content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first and last lines if they are markdown markers
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        return content

    @staticmethod
    def _create_model(model_name: str, temperature: float):
        """Instantiate a chat model based on provider prefix."""
        model = model_name
        if ":" in model_name:
            provider, model = model_name.split(":", 1)
        else:
            provider = "openai"
        if model.startswith("models/"):
            model = model.replace("models/", "")
        provider = provider.lower()
        if provider == "google":
            return ChatGoogleGenerativeAI(model=model, temperature=temperature)
        if provider == "openai":
            return ChatOpenAI(model=model, temperature=temperature)
        raise ValueError(f"Unsupported provider '{provider}'. Use google:* or openai:* model IDs.")
