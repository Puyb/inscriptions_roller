import os

import pytest

COURSE_PATH = '/e2e/'


@pytest.fixture(scope='session')
def base_url():
    return os.environ.get('BASE_URL', 'http://django-e2e:29000')
