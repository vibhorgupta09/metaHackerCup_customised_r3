import json
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI


class FinalJudgeAgent:
    """Agent that compares multiple candidate solutions and selects the most promising one."""

    def __init__(self, model_name: str):
        self.model = self._create_model(model_name, temperature=0.2)
        self.system_prompt = """You are a meticulous code judge.

Given a competitive programming problem and several candidate Python solutions (with metadata about prior automated tests),
carefully analyze each candidate's correctness, efficiency, and robustness. Favor implementations that already passed automated
tests (verdict=Accepted, output_match=True). If none passed, choose the one most likely to be correct and scalable.

Return your decision STRICTLY as a JSON object:
{
  "winner_attempt": <attempt_number>,
  "reason": "<short explanation>"
}

Do not include any other text."""

    def judge(self, problem_statement: str, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not candidates:
            return {}

        candidate_blocks = []
        for idx, candidate in enumerate(candidates, 1):
            code = candidate.get('code', '').strip()
            verdict = candidate.get('verdict')
            output_match = candidate.get('output_match')
            exec_success = candidate.get('execution_success')
            error_message = candidate.get('error_message')
            attempt_num = candidate.get('attempt_number')

            block = [
                f"Candidate {idx} (attempt {attempt_num}):",
                f"  Verdict: {verdict}",
                f"  Output match: {output_match}",
                f"  Execution success: {exec_success}",
                f"  Notes: {error_message or 'N/A'}",
                "  Code:",
                code,
                "  --- END CODE ---"
            ]
            candidate_blocks.append("\n".join(block))

        user_prompt = (
            "Problem Statement:\n"
            f"{problem_statement}\n\n"
            "Candidates:\n" + "\n\n".join(candidate_blocks) +
            "\n\nSelect the single best candidate and respond with the JSON format described earlier."
        )

        response = self.model.invoke(
            [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        content = response.content.strip()
        return self._parse_json_response(content)

    @staticmethod
    def _parse_json_response(text: str) -> Dict[str, Any]:
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except Exception:
            return {}

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
