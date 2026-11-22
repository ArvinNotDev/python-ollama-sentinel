import unittest

from core.thinking import resolve_thinking_controls


class ThinkingControlsTests(unittest.TestCase):
    def test_boolean_switch_is_optional_when_false_is_advertised(self):
        controls = resolve_thinking_controls({
            "capabilities": ["completion", "thinking"],
            "thinking": {"values": [True, False], "default": True},
        })
        self.assertTrue(controls.supported)
        self.assertFalse(controls.required)
        self.assertEqual(controls.values, (True, False))
        self.assertIs(controls.default, True)

    def test_named_levels_are_required_when_off_is_not_advertised(self):
        controls = resolve_thinking_controls({
            "capabilities": ["thinking"],
            "thinking": {"values": ["low", "medium", "high"], "default": "medium"},
        })
        self.assertTrue(controls.supported)
        self.assertTrue(controls.required)
        self.assertEqual(controls.levels, ("low", "medium", "high"))
        self.assertEqual(controls.default, "medium")

    def test_true_only_thinking_control_is_required(self):
        controls = resolve_thinking_controls({
            "thinking": {"values": [True], "default": True},
        })
        self.assertTrue(controls.supported)
        self.assertTrue(controls.required)

    def test_false_only_means_model_does_not_support_thinking(self):
        controls = resolve_thinking_controls({
            "capabilities": ["completion", "thinking"],
            "thinking": {"values": [False], "default": False},
        })
        self.assertFalse(controls.supported)
        self.assertFalse(controls.required)

    def test_capability_without_explicit_values_keeps_thinking_enabled(self):
        controls = resolve_thinking_controls({"capabilities": ["thinking"]})
        self.assertTrue(controls.supported)
        self.assertTrue(controls.required)
        self.assertEqual(controls.values, (True,))

    def test_missing_thinking_metadata_disables_control(self):
        controls = resolve_thinking_controls({"capabilities": ["completion"]})
        self.assertFalse(controls.supported)
        self.assertFalse(controls.required)


if __name__ == "__main__":
    unittest.main()
