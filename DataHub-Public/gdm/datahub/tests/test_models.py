from django.test import TestCase
from datahub.models import Tutorial
import datetime

class ModelTests(TestCase):

    def test_create_tutorial(self):
        """Creates and saves a new tutorial"""
        title = 'testing1'
        content = 'test is good'
        published = datetime.timezone.now()

        tutorial = Tutorial.objects.create(
            title=title,
			content=content,
			published=published
		)

        # tutorial.id

        self.assertEqual(tutorial.title, title)

