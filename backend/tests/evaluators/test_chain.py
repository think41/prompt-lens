import json
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../"))

from app.evaluators.length import LengthEvaluator
from app.evaluators.vagueness import VaguenessEvaluator
from app.evaluators.context import ContextEvaluator
from app.evaluators.security import SecurityEvaluator
from app.evaluators.chain import EvaluatorChain

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures/golden_prompts.json")


class TestLengthEvaluator(unittest.TestCase):
    def setUp(self):
        self.ev = LengthEvaluator()

    def test_too_short(self):
        delta, flags = self.ev.evaluate(10)
        self.assertLess(delta, 0)
        self.assertIn("too_short", flags)

    def test_too_long(self):
        delta, flags = self.ev.evaluate(3000)
        self.assertLess(delta, 0)
        self.assertIn("too_long", flags)

    def test_optimal_range(self):
        delta, flags = self.ev.evaluate(200)
        self.assertGreater(delta, 0)
        self.assertEqual(flags, [])

    def test_normal_no_flags(self):
        delta, flags = self.ev.evaluate(50)
        self.assertEqual(delta, 0.0)
        self.assertEqual(flags, [])


class TestVaguenessEvaluator(unittest.TestCase):
    def setUp(self):
        self.ev = VaguenessEvaluator()

    def test_vague_phrase(self):
        delta, flags = self.ev.evaluate("fix it please")
        self.assertLess(delta, 0)
        self.assertIn("vague", flags)

    def test_multiple_vague_phrases(self):
        delta, flags = self.ev.evaluate("fix it and make it work and help me")
        self.assertLessEqual(delta, -0.3)
        self.assertIn("vague", flags)

    def test_no_vague_phrases(self):
        delta, flags = self.ev.evaluate("Refactor the authentication middleware to use JWT")
        self.assertEqual(delta, 0.0)
        self.assertEqual(flags, [])

    def test_max_penalty_capped(self):
        delta, flags = self.ev.evaluate("fix it do it help me make it work not working broken")
        self.assertGreaterEqual(delta, -self.ev.max_penalty)


class TestContextEvaluator(unittest.TestCase):
    def setUp(self):
        self.ev = ContextEvaluator()

    def test_code_block_has_context(self):
        delta, flags = self.ev.evaluate("```python\ndef foo(): pass\n```")
        self.assertEqual(delta, 0.0)
        self.assertEqual(flags, [])

    def test_error_message_has_context(self):
        delta, flags = self.ev.evaluate("Getting a TypeError when calling the function")
        self.assertEqual(delta, 0.0)

    def test_short_prompt_skipped(self):
        delta, flags = self.ev.evaluate("fix it")
        self.assertEqual(delta, 0.0)

    def test_missing_context(self):
        delta, flags = self.ev.evaluate("How do I add authentication to my app and make it secure?")
        self.assertLess(delta, 0)
        self.assertIn("missing_context", flags)


class TestSecurityEvaluator(unittest.TestCase):
    def setUp(self):
        self.ev = SecurityEvaluator()

    def test_env_file(self):
        delta, flags = self.ev.evaluate("update the .env file with the new key")
        self.assertLess(delta, 0)
        self.assertIn("sensitive_content", flags)

    def test_aws_secret(self):
        delta, flags = self.ev.evaluate("my AWS_SECRET_KEY is AKIAIOSFODNN7EXAMPLE")
        self.assertLess(delta, 0)
        self.assertIn("sensitive_content", flags)

    def test_clean_prompt(self):
        delta, flags = self.ev.evaluate("add pagination to the sessions endpoint")
        self.assertEqual(delta, 0.0)
        self.assertEqual(flags, [])

    def test_max_penalty_capped(self):
        delta, flags = self.ev.evaluate(
            "update .env and credentials and private_key and api_key and aws_secret and id_rsa"
        )
        self.assertGreaterEqual(delta, -self.ev.max_penalty)


class TestEvaluatorChain(unittest.TestCase):
    def setUp(self):
        self.chain = EvaluatorChain()

    def test_score_in_range(self):
        score, _ = self.chain.score("anything", 8)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_golden_prompts(self):
        with open(FIXTURES) as f:
            prompts = json.load(f)

        failures = []
        for p in prompts:
            score, flags = self.chain.score(p["prompt"], len(p["prompt"]))

            if "expected_min_score" in p and score < p["expected_min_score"]:
                failures.append(
                    f"ID {p['id']} ({p['tier']}): score {score} < min {p['expected_min_score']} | prompt: {p['prompt'][:60]!r}"
                )
            if "expected_max_score" in p and score > p["expected_max_score"]:
                failures.append(
                    f"ID {p['id']} ({p['tier']}): score {score} > max {p['expected_max_score']} | prompt: {p['prompt'][:60]!r}"
                )
            for expected_flag in p.get("expected_flags", []):
                if expected_flag not in flags:
                    failures.append(
                        f"ID {p['id']}: expected flag '{expected_flag}' not in {flags}"
                    )

        if failures:
            self.fail("Golden prompt failures:\n" + "\n".join(failures))

    def test_high_quality_prompt(self):
        prompt = "Getting TypeError in line 42 of /app/api/sessions.py:\n```python\nreturn db.query(Turn).filter_by(session_id=sid).all()\n```\nError: session_id column not found. Schema uses 'id' not 'session_id'."
        score, flags = self.chain.score(prompt, len(prompt))
        self.assertGreaterEqual(score, 0.7)

    def test_vague_short_prompt(self):
        score, flags = self.chain.score("fix it", len("fix it"))
        self.assertLessEqual(score, 0.55)
        self.assertIn("vague", flags)


if __name__ == "__main__":
    unittest.main()
