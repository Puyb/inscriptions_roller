"""Category form (`custom_admin/categorie.js`): the course field is filled
from the `course_id` cookie and hidden, and the price fields are replaced by
a table with one column per price step (opening date + each increase date),
which writes back into the hidden `prices_base` / `prices_equipier` fields."""
import re

from playwright.sync_api import expect


def open_category(page, code='SOLO'):
    page.goto('/course/inscriptions/categorie/')
    page.locator('#result_list tbody tr', has_text=code).locator('a').first.click()
    expect(page).to_have_url(re.compile(r'/categorie/\d+/change/$'))


def test_course_field_is_filled_from_cookie_and_hidden(admin_page):
    open_category(admin_page)
    course_id = next(c['value'] for c in admin_page.context.cookies() if c['name'] == 'course_id')
    expect(admin_page.locator('#id_course')).to_have_value(course_id)
    expect(admin_page.locator('.form-row.field-course')).to_be_hidden()


def test_price_table_has_one_column_per_price_step(admin_page):
    open_category(admin_page)
    # opening date + 1 increase date = 2 steps
    expect(admin_page.locator('input[name^=prices_base__]')).to_have_count(2)
    expect(admin_page.locator('input[name^=prices_equipier__]')).to_have_count(2)
    expect(admin_page.locator('input[name=prices_base__0]')).to_have_value('30.00')
    expect(admin_page.locator('input[name=prices_base__1]')).to_have_value('35.00')
    # a missing equipier price falls back to the last known one (0)
    expect(admin_page.locator('input[name=prices_equipier__0]')).to_have_value('0')
    expect(admin_page.locator('.form-row.field-prices_base')).to_be_hidden()
    expect(admin_page.locator('.form-row.field-prices_equipier')).to_be_hidden()


def test_editing_price_table_updates_hidden_fields_and_is_saved(admin_page):
    open_category(admin_page, 'DUO')
    admin_page.fill('input[name=prices_base__1]', '55')
    admin_page.fill('input[name=prices_equipier__1]', '12')
    # `change` fires on blur
    admin_page.locator('input[name=prices_equipier__1]').blur()
    expect(admin_page.locator('#id_prices_base')).to_have_value(re.compile(r'^40(\.00)?,55$'))
    expect(admin_page.locator('#id_prices_equipier')).to_have_value(re.compile(r'^10(\.00)?,12$'))

    admin_page.click('[name=_save]')
    expect(admin_page).to_have_url(re.compile(r'/course/inscriptions/categorie/$'))

    open_category(admin_page, 'DUO')
    expect(admin_page.locator('input[name=prices_base__1]')).to_have_value(re.compile(r'^55(\.00)?$'))
    expect(admin_page.locator('input[name=prices_equipier__1]')).to_have_value(re.compile(r'^12(\.00)?$'))
