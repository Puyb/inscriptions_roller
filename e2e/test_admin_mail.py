"""Sent mail detail page (`custom_admin/mail.js`): the HTML body is moved out
of the read-only field and rendered below the form."""
import re

from playwright.sync_api import expect


def test_mail_body_is_rendered_as_html(admin_page):
    admin_page.goto('/course/inscriptions/mail/')
    admin_page.locator('#result_list tbody tr', has_text='Sujet e2e').locator('a').first.click()
    expect(admin_page).to_have_url(re.compile(r'/mail/\d+/change/'))
    expect(admin_page.locator('.field-message')).to_have_count(0)
    expect(admin_page.locator('#mail-body')).to_be_visible()
    expect(admin_page.locator('#mail-body b')).to_have_text('riche')
