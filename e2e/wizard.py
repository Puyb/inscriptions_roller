"""Helpers to drive the multi-page registration wizard (`form.js`).

The wizard has no server round-trip between pages: page 0 (team/manager
info) picks a team size, one page per equipier is shown/hidden with plain
JS, then a last page lets the browser pick an eligible category (computed
client-side from `CATEGORIES`) before the real POST submit.
"""
from datetime import date

from playwright.sync_api import Page

ADULT_YEAR = date.today().year - 30
MINOR_YEAR = date.today().year - 10


def fill_equipe_page(page: Page, nom, nombre, gerant_nom='Dupont', gerant_prenom='Jean', email=None):
    email = email or ('%s@example.com' % nom.lower().replace(' ', '.'))
    page.fill('#id_nom', nom)
    page.fill('#id_gerant_nom', gerant_nom)
    page.fill('#id_gerant_prenom', gerant_prenom)
    page.fill('#id_gerant_ville', 'Paris')
    page.fill('#id_gerant_code_postal', '75000')
    page.fill('#id_gerant_email', email)
    page.fill('#id_gerant_email2', email)
    page.fill('#id_gerant_telephone', '0102030405')
    page.select_option('#id_nombre', str(nombre))


def fill_equipier_page(page: Page, index, nom, prenom, sexe, year=ADULT_YEAR,
                        justificatif='certificat', num_licence='', month=1, day=1):
    prefix = '#id_form-%d-' % index
    page.fill(prefix + 'nom', nom)
    page.fill(prefix + 'prenom', prenom)
    page.select_option(prefix + 'sexe', sexe)
    page.select_option(prefix + 'date_de_naissance_year', str(year))
    page.select_option(prefix + 'date_de_naissance_month', str(month))
    page.select_option(prefix + 'date_de_naissance_day', str(day))
    if justificatif == 'licence':
        page.check(prefix + 'justificatif_1')
        page.fill(prefix + 'num_licence', num_licence or '123456')
    else:
        page.check(prefix + 'justificatif_2')


def go_next(page: Page):
    page.click('#button_next')


def go_prev(page: Page):
    page.click('#button_prev')


def register_full_team(page: Page, nom, nombre, equipiers, course_path='/e2e/'):
    """equipiers: list of dicts with nom/prenom/sexe/year/justificatif/num_licence."""
    page.goto(course_path)
    fill_equipe_page(page, nom=nom, nombre=nombre)
    go_next(page)
    for i, equipier in enumerate(equipiers):
        fill_equipier_page(page, i, **equipier)
        go_next(page)
    page.check('#catwrapper input[type=radio] >> nth=0')
    page.check('#id_conditions')
    page.click('#button_submit')
