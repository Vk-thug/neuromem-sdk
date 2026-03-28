"""
LLM-as-a-Judge evaluator for memory system benchmarks.

Uses an LLM to score answer quality on a 1-5 scale, matching the
evaluation methodology used in LoCoMo and Mem0 benchmarks.

Supports both Ollama (local) and OpenAI models.
"""

import json
import re
from typing import Optional


JUDGE_SYSTEM_PROMPT = """You are an expert evaluator for a memory system benchmark.
Your task is to score how well a generated answer matches the ground truth answer.

Score on a scale of 1-5:
  5 = Perfect match — answer is factually identical to ground truth
  4 = Near perfect — answer captures all key facts with minor differences
  3 = Partially correct — answer captures some but not all key facts
  2 = Mostly wrong — answer has some tangential relevance but misses the point
  1 = Completely wrong — answer is factually incorrect or irrelevant

For adversarial/unanswerable questions:
  5 = Correctly identifies the question as unanswerable or based on a false premise
  4 = Expresses uncertainty and doesn't give a wrong answer
  3 = Gives a hedged answer that's partially wrong
  2 = Gives a confident wrong answer
  1 = Gives a completely wrong answer with full confidence

Return ONLY a JSON object with two fields:
  {"score": <1-5>, "reasoning": "<brief explanation>"}"""


JUDGE_USER_TEMPLATE = """Question: {question}

Ground Truth Answer: {ground_truth}

Generated Answer: {prediction}

Evaluate the generated answer against the ground truth. Return JSON only."""


class LLMJudge:
    """LLM-based answer quality evaluator."""

    def __init__(
        self,
        model: str = "qwen2.5-coder:7b",
        provider: str = "ollama",
        ollama_base_url: str = "http://localhost:11434",
    ) -> None:
        self.model = model
        self.provider = provider
        self.ollama_base_url = ollama_base_url
        self._client = None

    def _get_client(self):
        """Lazy-init the LLM client."""
        if self._client is not None:
            return self._client

        if self.provider == "ollama":
            try:
                import ollama
                self._client = ollama.Client(host=self.ollama_base_url)
            except ImportError:
                raise ImportError("ollama package required: pip install ollama")
        elif self.provider == "openai":
            try:
                import openai
                self._client = openai.OpenAI()
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        elif self.provider == "litellm":
            try:
                import litellm
                self._client = litellm
            except ImportError:
                raise ImportError("litellm package required: pip install litellm")
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

        return self._client

    def score(
        self,
        question: str,
        ground_truth: str,
        prediction: str,
        is_adversarial: bool = False,
    ) -> dict:
        """
        Score a prediction against ground truth using LLM-as-a-Judge.

        Args:
            question: The original question
            ground_truth: Expected answer
            prediction: Generated answer to evaluate
            is_adversarial: Whether this is an adversarial (unanswerable) question

        Returns:
            {"score": 1-5, "reasoning": str}
        """
        user_msg = JUDGE_USER_TEMPLATE.format(
            question=question,
            ground_truth=ground_truth if not is_adversarial else f"{ground_truth} (Note: this question is unanswerable/adversarial)",
            prediction=prediction,
        )

        try:
            response_text = self._call_llm(user_msg)
            return self._parse_judge_response(response_text)
        except Exception as e:
            return {"score": 0, "reasoning": f"Judge error: {e}"}

    def _call_llm(self, user_msg: str) -> str:
        """Call the LLM and return raw response text."""
        client = self._get_client()

        if self.provider == "ollama":
            response = client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
            )
            return response["message"]["content"]

        elif self.provider == "openai":
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=200,
            )
            return response.choices[0].message.content

        elif self.provider == "litellm":
            response = client.completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=200,
            )
            return response.choices[0].message.content

        raise ValueError(f"Unknown provider: {self.provider}")

    def _parse_judge_response(self, text: str) -> dict:
        """Parse the judge's JSON response, with fallback regex extraction."""
        # Try JSON parse first
        try:
            # Find JSON in response
            json_match = re.search(r"\{[^}]+\}", text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                score = int(result.get("score", 0))
                reasoning = str(result.get("reasoning", ""))
                return {"score": max(1, min(5, score)), "reasoning": reasoning}
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: extract score from text
        score_match = re.search(r"(?:score|rating)[:\s]*(\d)", text, re.IGNORECASE)
        if score_match:
            score = int(score_match.group(1))
            return {"score": max(1, min(5, score)), "reasoning": text[:200]}

        # Last resort: look for any standalone digit 1-5
        digit_match = re.search(r"\b([1-5])\b", text)
        if digit_match:
            return {"score": int(digit_match.group(1)), "reasoning": text[:200]}

        return {"score": 0, "reasoning": f"Could not parse judge response: {text[:100]}"}
