import unittest

from guardrails import is_topic_allowed


class TopicGuardrailTests(unittest.TestCase):
    def test_unmatched_cooking_questions_are_allowed(self):
        self.assertEqual(is_topic_allowed("How do I keep pasta from sticking?"), (True, "ok"))

    def test_conversational_openers_are_allowed(self):
        self.assertEqual(is_topic_allowed("Hello"), (True, "ok"))

    def test_blocked_topics_are_still_rejected(self):
        allowed, message = is_topic_allowed("Tell me about politics")

        self.assertFalse(allowed)
        self.assertEqual(message, "I can only help with food-related questions and marketplace inquiries.")


if __name__ == "__main__":
    unittest.main()
