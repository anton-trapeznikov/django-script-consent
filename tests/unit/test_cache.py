from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from script_consent.cache import get_runtime_state, invalidate_runtime_cache


def _category(**kwargs):
    defaults = dict(
        id=1,
        code="technical",
        title="Essential",
        description="",
        is_required=True,
        order=0,
        is_active=True,
    )
    defaults.update(kwargs)
    return MagicMock(**defaults)


def _script(**kwargs):
    cat = kwargs.pop("category", None) or _category()
    defaults = dict(
        id=1,
        name="S",
        category_id=cat.id,
        category=cat,
        always_load=False,
        placement="body_end",
        code="<script></script>",
        order=0,
        is_active=True,
    )
    defaults.update(kwargs)
    s = MagicMock()
    for k, v in defaults.items():
        setattr(s, k, v)
    return s


class GetRuntimeStateTests(SimpleTestCase):
    @patch("script_consent.cache.cache")
    @patch("script_consent.cache.repositories")
    def test_with_active_banner(self, repos, dj_cache):
        dj_cache.get.return_value = None
        banner = MagicMock(id=7, title="T", text="txt", version=3, is_active=True)
        cat = _category(id=1, code="analytics", is_required=False)
        script = _script(id=5, category=cat, category_id=1)
        repos.cache_stamp_current.return_value = 1
        repos.get_active_banner.return_value = banner
        repos.list_active_categories.return_value = [cat]
        repos.list_active_scripts.return_value = [script]

        state = get_runtime_state()

        self.assertEqual(state["banner"]["id"], 7)
        self.assertEqual(state["version"], 3)
        self.assertEqual(len(state["scripts"]), 1)
        self.assertTrue(state["scripts"][0]["requires_consent"])
        self.assertTrue(state["has_consent_gated_scripts"])
        self.assertEqual(len(state["scripts_hash"]), 64)
        dj_cache.set.assert_called_once()
        args, kwargs = dj_cache.set.call_args
        self.assertEqual(args[1], state)

    @patch("script_consent.cache.cache")
    @patch("script_consent.cache.repositories")
    def test_without_banner(self, repos, dj_cache):
        dj_cache.get.return_value = None
        cat = _category()
        repos.cache_stamp_current.return_value = 0
        repos.get_active_banner.return_value = None
        repos.list_active_categories.return_value = [cat]
        repos.list_active_scripts.return_value = []

        state = get_runtime_state()

        self.assertIsNone(state["banner"])
        self.assertEqual(state["version"], 0)
        self.assertEqual(state["scripts"], [])
        self.assertFalse(state["has_consent_gated_scripts"])
        repos.get_active_banner.assert_called_once_with()

    @patch("script_consent.cache.cache")
    @patch("script_consent.cache.repositories")
    def test_cache_hit_skips_repositories(self, repos, dj_cache):
        cached = {"banner": None, "version": 0, "scripts": []}
        dj_cache.get.return_value = cached
        repos.cache_stamp_current.return_value = 0

        state = get_runtime_state()

        self.assertIs(state, cached)
        repos.get_active_banner.assert_not_called()
        repos.list_active_scripts.assert_not_called()


class InvalidateRuntimeCacheTests(SimpleTestCase):
    @patch("script_consent.cache.cache")
    @patch("script_consent.cache.repositories")
    def test_bumps_stamp_and_deletes_keys(self, repos, dj_cache):
        repos.cache_stamp_current.return_value = 5
        repos.cache_stamp_bump.return_value = 6

        invalidate_runtime_cache()

        repos.cache_stamp_bump.assert_called_once_with()
        self.assertTrue(dj_cache.delete.called)
