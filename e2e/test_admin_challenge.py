"""Challenge pages of the superuser admin (`/admin/`): creation form
(`admin_create_challenge.js`) and course selection page
(`admin/challenge/courses.html`)."""
import re

from playwright.sync_api import expect


def test_choosing_a_course_model_lists_its_categories(super_page):
    super_page.goto('/admin/inscriptions/challenge/add/')
    super_page.check('[name=course_model][value=paris]')
    table = super_page.locator('fieldset .form-row', has_text='Catégories').locator('table')
    expect(table.locator('th', has_text=re.compile('^IDH$'))).to_have_count(1)
    expect(table.locator('td', has_text='Individuel Homme')).to_have_count(1)
    super_page.check('[name=course_model][value=grol]')
    expect(table.locator('th', has_text=re.compile('^IDH$'))).to_have_count(0)


def test_creating_a_challenge_copies_the_model_categories(super_page):
    super_page.goto('/admin/inscriptions/challenge/add/')
    super_page.fill('#id_nom', 'Challenge cree par e2e')
    super_page.fill('#id_uid', 'e2enewchal')
    super_page.select_option('#id_mode', 'nord2017')
    super_page.check('[name=course_model][value=paris]')
    super_page.click('[name=_save]')
    expect(super_page).to_have_url(re.compile(r'/admin/inscriptions/challenge/$'))
    super_page.locator('#result_list').get_by_role('link', name='Challenge cree par e2e').click()
    expect(super_page.locator('input[value=IDH]')).to_have_count(1)


def manage_courses(page):
    page.goto('/admin/inscriptions/challenge/')
    page.locator('#result_list tbody tr', has_text='Challenge E2E').locator('input.action-select').check()
    page.select_option('select[name=action]', 'manage_courses')
    page.locator('.actions button[type=submit], .actions input[type=submit]').first.click()
    expect(page.locator('#id_courses')).to_be_visible()


def test_course_blocks_follow_the_selection(super_page):
    manage_courses(super_page)
    block = super_page.locator('#course_%s' % super_page.locator('#id_courses option', has_text='(e2e)').get_attribute('value'))
    expect(block).to_be_hidden()
    super_page.select_option('#id_courses', label='Course E2E (e2e)')
    expect(block).to_be_visible()
    super_page.select_option('#id_courses', [])
    expect(block).to_be_hidden()
