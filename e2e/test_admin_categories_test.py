"""Category simulator (`admin/test_categories.html`): evaluates every
category rule (team size, age, sex, custom JS) against a fictional team."""
import re

from playwright.sync_api import expect

URL = '/course/inscriptions/categorie/test/'
OK, KO = '✅', '🚫'


def result(page, code):
    """Cells: code, nombre, age, sexe, valid, final."""
    row = page.locator('#result tbody tr', has=page.locator('td', has_text=re.compile('^%s$' % code)))
    return row.locator('td').all_inner_texts()[1:]


def set_nombre(page, n):
    page.fill('#nombre', str(n))
    page.locator('#nombre').dispatch_event('change')


def test_one_row_per_category_with_a_solo_default(admin_page):
    admin_page.goto(URL)
    expect(admin_page.locator('#result tbody tr')).to_have_count(3)
    assert result(admin_page, 'SOLO') == [OK, OK, OK, OK, OK]
    assert result(admin_page, 'DUO')[0] == KO
    assert result(admin_page, 'DUO')[-1] == KO


def test_only_the_first_n_equipier_rows_are_shown(admin_page):
    admin_page.goto(URL)
    expect(admin_page.locator('#equipiers tbody tr:visible')).to_have_count(1)
    set_nombre(admin_page, 3)
    expect(admin_page.locator('#equipiers tbody tr:visible')).to_have_count(3)


def test_team_size_selects_matching_categories(admin_page):
    admin_page.goto(URL)
    set_nombre(admin_page, 2)
    assert result(admin_page, 'DUO')[-1] == OK
    assert result(admin_page, 'SOLO')[-1] == KO
    set_nombre(admin_page, 4)
    assert result(admin_page, 'TRIO')[-1] == OK
    assert result(admin_page, 'DUO')[-1] == KO


def test_age_rule_uses_the_youngest_equipier(admin_page):
    admin_page.goto(URL)
    admin_page.fill('#equipier1_age', '13')
    admin_page.locator('#equipier1_age').dispatch_event('change')
    assert result(admin_page, 'SOLO')[1] == KO     # solo: min age 15
    set_nombre(admin_page, 3)
    admin_page.fill('#equipier1_age', '13')
    admin_page.locator('#equipier1_age').dispatch_event('change')
    assert result(admin_page, 'TRIO')[-1] == OK   # trio: min age 12


def test_data_panel_reflects_the_simulated_team(admin_page):
    admin_page.goto(URL)
    set_nombre(admin_page, 2)
    admin_page.select_option('#equipier2_sexe', 'F')
    data = admin_page.evaluate("JSON.parse($('#data').text())")
    assert data['nombre'] == 2
    assert data['nombre_h'] == 1 and data['nombre_f'] == 1
    assert data['age_moyen'] == 18
