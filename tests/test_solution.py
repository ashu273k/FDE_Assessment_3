import unittest

from src.solution import handle_request


class SolutionTests(unittest.TestCase):
    def test_injection_is_data_and_missing_fields_block(self):
        decision = handle_request("REQ-1006")
        self.assertIn("missing_information", decision.risk_flags)
        self.assertIn("prompt_injection_detected", decision.risk_flags)
        self.assertTrue(decision.human_review_required)

    def test_risk_outage_is_conservative(self):
        decision = handle_request("REQ-1009")
        self.assertIn("vendor_risk_unavailable", decision.risk_flags)
        self.assertIn("Security", decision.required_approvals)
        self.assertTrue(decision.human_review_required)

    def test_staged_has_explicit_handoff(self):
        decision = handle_request("REQ-1001", architecture="staged")
        self.assertIn("staged_evidence_handoff", decision.telemetry.tool_names)
        self.assertEqual(decision.telemetry.llm_calls, 0)


if __name__ == "__main__":
    unittest.main()