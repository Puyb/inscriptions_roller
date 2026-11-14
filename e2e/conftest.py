import os

import pytest

COURSE_PATH = '/e2e/e2e/'
ADMIN_USERNAME = 'e2e-admin'
ADMIN_PASSWORD = 'e2e-password'
SUPER_USERNAME = 'e2e-super'


@pytest.fixture(scope='session')
def base_url():
    return os.environ.get('BASE_URL', 'http://django-e2e:29000')


def login_state(browser, base_url, tmp_path_factory, username, filename):
    context = browser.new_context(base_url=base_url)
    page = context.new_page()
    page.goto('/course/login/')
    page.fill('#id_username', username)
    page.fill('#id_password', ADMIN_PASSWORD)
    page.click('input[type=submit]')
    page.wait_for_url(lambda url: '/login/' not in url)
    path = tmp_path_factory.mktemp('state') / filename
    context.storage_state(path=str(path))
    context.close()
    return str(path)


@pytest.fixture(scope='session')
def admin_storage_state(browser, base_url, tmp_path_factory):
    """Log into the course backoffice once and reuse the session cookie."""
    return login_state(browser, base_url, tmp_path_factory, ADMIN_USERNAME, 'admin.json')


@pytest.fixture(scope='session')
def super_storage_state(browser, base_url, tmp_path_factory):
    return login_state(browser, base_url, tmp_path_factory, SUPER_USERNAME, 'super.json')


@pytest.fixture
def super_page(browser, base_url, super_storage_state):
    """Logged in as superuser, no course cookie."""
    context = browser.new_context(base_url=base_url, storage_state=super_storage_state)
    yield context.new_page()
    context.close()


@pytest.fixture
def bare_admin_page(browser, base_url, admin_storage_state):
    """Logged in as organizer, but no course cookie yet."""
    context = browser.new_context(base_url=base_url, storage_state=admin_storage_state)
    yield context.new_page()
    context.close()


@pytest.fixture
def admin_page(browser, base_url, admin_storage_state):
    """A page logged in as organizer, with the course cookies set
    (course_uid/course_id/course_nom) by the `/e2e/e2e/admin/` redirect."""
    context = browser.new_context(base_url=base_url, storage_state=admin_storage_state)
    page = context.new_page()
    page.goto('/e2e/e2e/admin/')
    yield page
    context.close()
