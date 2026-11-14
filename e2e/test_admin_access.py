"""Course selection and access control around `admin.js`, `dashboard.html`
and `CourseAdminSite.has_permission`."""
import re

from playwright.sync_api import expect


def test_dashboard_without_course_redirects_to_choose(bare_admin_page):
    page = bare_admin_page
    page.goto('/course/')
    expect(page).to_have_url(re.compile(r'/course/choose/$'))
    expect(page.get_by_text('Sélectionnez votre course')).to_be_visible()


def test_choosing_a_course_sets_cookies_and_opens_its_dashboard(bare_admin_page):
    page = bare_admin_page
    page.goto('/course/choose/')
    page.get_by_role('link', name=re.compile('Course E2E')).click()
    expect(page).to_have_url(re.compile(r'/course/$'))
    cookies = {c['name']: c['value'] for c in page.context.cookies()}
    assert cookies['course_uid'].strip('"') == 'e2e/e2e'
    assert cookies['course_nom']
    expect(page.locator('#site-name')).to_contain_text('Course E2E')


def test_course_without_accreditation_is_not_listed(bare_admin_page):
    page = bare_admin_page
    page.goto('/course/choose/')
    expect(page.get_by_role('link', name=re.compile('Course E2E'))).to_be_visible()
    expect(page.get_by_text('Course Autre E2E')).to_have_count(0)


def test_js_redirects_to_choose_when_cookie_course_is_not_accredited(bare_admin_page):
    """/course/ itself is reachable by any logged user, so only `admin.js`
    notices that the cookie points to a course the user cannot manage."""
    page = bare_admin_page
    page.goto('/course/choose/')
    base = re.match(r'(https?://[^/]+)', page.url).group(1)
    page.context.add_cookies([dict(name='course_uid', value='e2eother/e2eother', url=base)])
    page.goto('/course/')
    expect(page).to_have_url(re.compile(r'/course/choose/$'))


def test_backoffice_pages_are_refused_for_a_non_accredited_course(bare_admin_page):
    page = bare_admin_page
    page.goto('/course/choose/')
    base = re.match(r'(https?://[^/]+)', page.url).group(1)
    page.context.add_cookies([dict(name='course_uid', value='e2eother/e2eother', url=base)])
    page.goto('/course/inscriptions/equipe/')
    expect(page).to_have_url(re.compile(r'/course/login/\?next='))
    expect(page.locator('#result_list')).to_have_count(0)


def test_superuser_visiting_main_admin_clears_the_course_cookie(super_page):
    page = super_page
    page.goto('/e2e/e2e/admin/')
    assert any(c['name'] == 'course_uid' for c in page.context.cookies())
    page.goto('/admin/')
    assert not any(c['name'] == 'course_uid' and c['value'] for c in page.context.cookies())
