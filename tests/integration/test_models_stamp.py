import random

from django.test import TestCase

from script_consent.models import RuntimeCacheStamp


class RuntimeCacheStampTests(TestCase):
    def setUp(self):
        RuntimeCacheStamp.objects.all().delete()

    def test_current_creates_default_when_missing(self):
        self.assertEqual(RuntimeCacheStamp.current(), 0)
        self.assertTrue(RuntimeCacheStamp.objects.filter(pk=1).exists())
        stamp = RuntimeCacheStamp.objects.get(pk=1)
        self.assertEqual(stamp.generation, 0)

    def test_current_exists(self):
        generation = random.randint(1, 1_000_000)
        RuntimeCacheStamp.objects.create(pk=1, generation=generation)
        self.assertEqual(RuntimeCacheStamp.current(), generation)

    def test_bump_increments_generation(self):
        generation = random.randint(1, 1_000_000)
        RuntimeCacheStamp.objects.create(pk=1, generation=generation)
        new_gen = RuntimeCacheStamp.bump()
        self.assertEqual(new_gen, generation + 1)
        self.assertEqual(RuntimeCacheStamp.current(), generation + 1)

    def test_bump_creates_if_missing(self):
        gen = RuntimeCacheStamp.bump()
        self.assertEqual(gen, 1)
        self.assertEqual(RuntimeCacheStamp.current(), 1)
