"""Results import form (inline PapaParse script in `import_resultat_form.html`):
each CSV input gets a 4-line preview, a detected delimiter, and its column
number inputs are replaced by selects listing the CSV columns."""
import re

from playwright.sync_api import expect

URL = '/course/resultats/'
EQUIPES_CSV = (
    'Dossard;Nom;Tours;Temps\n'
    '100;Alpha;10;3600\n'
    '101;Beta;9;3650\n'
    '102;Gamma;8;3700\n'
    '103;Delta;7;3800\n'
    '104;Epsilon;6;3900\n'
)
# same delimiter as EQUIPES_CSV: the form has a single, shared delimiter field
TOURS_CSV = 'Dossard;Duree;Heure\n100;360;36000\n101;365;36010\n'


def upload(page, field, name, content):
    page.set_input_files('[name=%s]' % field, files=[dict(name=name, mimeType='text/csv', buffer=content.encode())])


def test_column_inputs_become_selects(admin_page):
    admin_page.goto(URL)
    for name in ('dossard_column', 'time_column', 'nbtours_column', 'nom_column',
                 'tours_dossard_column', 'tours_duree_column', 'tours_timestamp_column'):
        expect(admin_page.locator('select[name=%s]' % name)).to_have_count(1)
        expect(admin_page.locator('input[name=%s]' % name)).to_have_count(0)


def test_uploading_a_csv_shows_preview_and_fills_column_choices(admin_page):
    admin_page.goto(URL)
    upload(admin_page, 'csv', 'equipes.csv', EQUIPES_CSV)

    preview = admin_page.locator('input[name=csv]').locator('xpath=ancestor::p/following-sibling::p[1]')
    expect(preview.locator('tr')).to_have_count(4)     # preview: 4 lines
    expect(preview.locator('tr').first).to_contain_text('Dossard')

    options = admin_page.locator('select[name=dossard_column] option')
    expect(options).to_have_count(5)                   # blank + 4 columns
    expect(options.nth(1)).to_have_text('Colonne 1 - Dossard')
    expect(options.nth(4)).to_have_text('Colonne 4 - Temps')
    # the equipes selects and the tours selects are independent
    expect(admin_page.locator('select[name=tours_dossard_column] option')).to_have_count(0)


def test_delimiter_is_autodetected(admin_page):
    admin_page.goto(URL)
    upload(admin_page, 'csv', 'equipes.csv', EQUIPES_CSV)
    expect(admin_page.locator('[name=delimiter]')).to_have_value(';')
    upload(admin_page, 'tours_csv', 'tours.csv', TOURS_CSV)
    expect(admin_page.locator('select[name=tours_dossard_column] option')).to_have_count(4)


def test_time_format_is_shown_only_when_a_time_column_is_chosen(admin_page):
    """`<x>_format` is hidden until `<x>_column` is set (used to be broken:
    `for...in` over an array iterated indexes instead of names)."""
    admin_page.goto(URL)
    upload(admin_page, 'csv', 'equipes.csv', EQUIPES_CSV)
    fmt = admin_page.locator('[name=time_format]')
    expect(fmt).to_be_hidden()
    admin_page.select_option('select[name=time_column]', '4')
    expect(fmt).to_be_visible()
    admin_page.select_option('select[name=time_column]', '')
    expect(fmt).to_be_hidden()
