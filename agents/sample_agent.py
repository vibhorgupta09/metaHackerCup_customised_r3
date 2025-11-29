from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI


class SampleExtractorAgent:
    """Agent that extracts official sample input/output blocks from the problem statement."""

    def __init__(self, model_name: str):
        self.model = self._create_model(model_name, temperature=0.0)
        self.system_prompt = """You extract the official SAMPLE INPUT or SAMPLE OUTPUT for a competitive programming problem.

Rules:
- Output ONLY the raw text of the requested sample block, with no commentary, labels, or markdown.
- Preserve the exact whitespace and line structure from the statement.
- Do NOT invent or alter numbers.
- If multiple sample blocks exist, return the FIRST one shown.
- If the problem statement lacks the requested block, respond with the single word: NONE.
"""

    def extract(self, problem_statement: str, sample_type: str) -> str:
        """Extract the requested sample input or output block."""
        sample_type = sample_type.upper()
        if sample_type not in {"INPUT", "OUTPUT"}:
            raise ValueError("sample_type must be 'INPUT' or 'OUTPUT'")

        user_prompt = (
            f"Problem statement:\n\n{problem_statement}\n\n"
            f"Return ONLY the official SAMPLE {sample_type} block."
        )

        response = self.model.invoke(
            [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        content = response.content.strip()
        if content.upper() == "NONE":
            return ""

        if content.startswith("```"):
            lines = content.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        return content

    @staticmethod
    def _create_model(model_name: str, temperature: float):
        provider = "openai"
        model = model_name
        if ":" in model_name:
            provider, model = model_name.split(":", 1)
        if model.startswith("models/"):
            model = model.replace("models/", "")

        provider = provider.lower()
        if provider == "google":
            return ChatGoogleGenerativeAI(model=model, temperature=temperature)
        if provider == "openai":
            return ChatOpenAI(model=model, temperature=temperature)
        raise ValueError(f"Unsupported provider '{provider}'. Use google:* or openai:* model IDs.")
