from django.test import TestCase
from .models import CachedArticle
class NewsMindTests(TestCase):
    def test_ai_summary_field_is_optional(self):
        field = CachedArticle._meta.get_field('ai_summary')
        self.assertTrue(field.blank)
        self.assertTrue(field.null)
    def test_project_loads(self):
        self.assertTrue(True)
