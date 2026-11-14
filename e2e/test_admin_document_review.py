"""Document review page (`document_review.html`): Oui / Non / Suivant buttons
fill a hidden field and submit the form; the comment is saved on the team.
Seeded with 5 teams "Document N" holding a document waiting for review; tests
only rely on the counter, not on which team comes first."""
import re

from playwright.sync_api import expect

URL = '/course/document/review/'


def counter(page):
    m = re.search(r'Document (\d+) / (\d+)', page.locator('h1', has_text='Document').first.inner_text())
    return int(m.group(1)), int(m.group(2))


def team_name(page):
    return page.locator('.field-nom p').first.inner_text()


def test_yes_validates_and_moves_to_next_document(admin_page):
    admin_page.goto(URL)
    index, count = counter(admin_page)
    assert index == 1 and count >= 2
    admin_page.get_by_role('button', name='Oui').click()
    admin_page.wait_for_load_state()
    assert counter(admin_page) == (1, count - 1)


def test_no_also_removes_it_from_the_queue(admin_page):
    admin_page.goto(URL)
    _, count = counter(admin_page)
    admin_page.get_by_role('button', name='Non').click()
    admin_page.wait_for_load_state()
    assert counter(admin_page) == (1, count - 1)


def test_next_skips_without_validating(admin_page):
    admin_page.goto(URL)
    first = team_name(admin_page)
    _, count = counter(admin_page)
    admin_page.get_by_role('button', name='Suivant').click()
    admin_page.wait_for_load_state()
    index, count_after = counter(admin_page)
    assert (index, count_after) == (2, count)
    assert team_name(admin_page) != first
    # skipped ids are kept in the form so the next skip moves on again
    assert admin_page.locator('[name=skip]').input_value() != ''


def test_comment_is_saved_on_the_team(admin_page):
    admin_page.goto(URL)
    name = team_name(admin_page)
    admin_page.fill('#id_commentaires', 'Certificat illisible e2e')
    admin_page.get_by_role('button', name='Oui').click()
    admin_page.wait_for_load_state()

    admin_page.goto('/course/inscriptions/equipe/?q=' + name.replace(' ', '+'))
    admin_page.locator('#result_list tbody tr', has_text=name).locator('a').first.click()
    expect(admin_page.locator('#id_commentaires')).to_have_value('Certificat illisible e2e')


def test_iframe_shows_the_uploaded_document(admin_page):
    admin_page.goto(URL)
    assert re.search(r'/uploads/.*\.pdf$|/media/.*\.pdf$|\.pdf$', admin_page.locator('iframe').get_attribute('src'))
