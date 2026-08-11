from django.test import SimpleTestCase

from script_consent.hashing import (
    compute_scripts_hash_from_rows,
    script_row_requires_consent,
)


class ScriptRowRequiresConsentTests(SimpleTestCase):
    def test_explicit_requires_consent(self):
        self.assertTrue(script_row_requires_consent({"requires_consent": True}))
        self.assertFalse(script_row_requires_consent({"requires_consent": False}))

    def test_always_load(self):
        self.assertFalse(
            script_row_requires_consent({"always_load": True, "is_required": False})
        )

    def test_required_category(self):
        self.assertFalse(
            script_row_requires_consent({"always_load": False, "is_required": True})
        )

    def test_optional_category(self):
        self.assertTrue(
            script_row_requires_consent({"always_load": False, "is_required": False})
        )


class ComputeScriptsHashFromRowsTests(SimpleTestCase):
    def _script(self, **overrides):
        row = {
            "id": 1,
            "category_id": 10,
            "category_code": "analytics",
            "placement": "body_end",
            "always_load": False,
            "is_required": False,
            "requires_consent": True,
            "code": "<script>1</script>",
            "order": 0,
        }
        row.update(overrides)
        return row

    def _category(self, **overrides):
        row = {
            "id": 10,
            "code": "analytics",
            "title": "Analytics",
            "description": "desc",
            "is_required": False,
            "order": 0,
        }
        row.update(overrides)
        return row

    def test_empty_is_stable(self):
        self.assertEqual(
            compute_scripts_hash_from_rows([]),
            compute_scripts_hash_from_rows([]),
        )
        self.assertEqual(len(compute_scripts_hash_from_rows([])), 64)

    def test_same_rows_same_hash(self):
        scripts = [self._script()]
        cats = [self._category()]
        self.assertEqual(
            compute_scripts_hash_from_rows(scripts, cats),
            compute_scripts_hash_from_rows(scripts, cats),
        )

    def test_code_change_changes_hash(self):
        a = compute_scripts_hash_from_rows([self._script(code="<script>1</script>")])
        b = compute_scripts_hash_from_rows([self._script(code="<script>2</script>")])
        self.assertNotEqual(a, b)

    def test_always_load_changes_hash(self):
        a = compute_scripts_hash_from_rows(
            [self._script(always_load=False, requires_consent=True)]
        )
        b = compute_scripts_hash_from_rows(
            [self._script(always_load=True, requires_consent=False)]
        )
        self.assertNotEqual(a, b)

    def test_is_required_changes_hash(self):
        a = compute_scripts_hash_from_rows(
            [self._script(is_required=False, requires_consent=True)]
        )
        b = compute_scripts_hash_from_rows(
            [self._script(is_required=True, requires_consent=False)]
        )
        self.assertNotEqual(a, b)

    def test_category_title_in_hash(self):
        scripts = [self._script()]
        a = compute_scripts_hash_from_rows(scripts, [self._category(title="Analytics")])
        b = compute_scripts_hash_from_rows(
            scripts, [self._category(title="Analytics (updated)")]
        )
        self.assertNotEqual(a, b)

    def test_category_description_in_hash(self):
        scripts = [self._script()]
        a = compute_scripts_hash_from_rows(scripts, [self._category(description="a")])
        b = compute_scripts_hash_from_rows(scripts, [self._category(description="b")])
        self.assertNotEqual(a, b)

    def test_order_independent_for_same_ids(self):
        s1 = self._script(id=1, order=10)
        s2 = self._script(id=2, order=0, code="<script>2</script>")
        a = compute_scripts_hash_from_rows([s1, s2])
        b = compute_scripts_hash_from_rows([s2, s1])
        self.assertEqual(a, b)

    def test_category_required_flag_in_hash(self):
        scripts = [self._script()]
        a = compute_scripts_hash_from_rows(scripts, [self._category(is_required=False)])
        b = compute_scripts_hash_from_rows(scripts, [self._category(is_required=True)])
        self.assertNotEqual(a, b)
