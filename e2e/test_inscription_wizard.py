import re

from playwright.sync_api import expect

from wizard import ADULT_YEAR, MINOR_YEAR, fill_equipe_page, fill_equipier_page, go_next, go_prev, register_full_team

COURSE_PATH = '/e2e/'


def test_solo_registration_completes_the_wizard(page):
    register_full_team(page, nom='Equipe Solo E2E', nombre=1, equipiers=[
        dict(nom='Dupont', prenom='Jean', sexe='H', year=ADULT_YEAR),
    ])
    expect(page).to_have_url(re.compile(r'/e2e/\d+/done/$'))


def test_page_count_matches_selected_team_size(page):
    """3 equipiers -> exactly 3 dynamic pages before the category page,
    not 1 (nombre isn't used) and not the 8 forms always rendered in the DOM."""
    page.goto(COURSE_PATH)
    fill_equipe_page(page, nom='Equipe Trio E2E', nombre=3)
    go_next(page)
    expect(page.locator('#part1')).to_be_visible()
    expect(page.locator('#part2')).to_be_hidden()

    fill_equipier_page(page, 0, nom='Un', prenom='Membre', sexe='H', year=ADULT_YEAR)
    go_next(page)
    expect(page.locator('#part2')).to_be_visible()
    expect(page.locator('#part3')).to_be_hidden()
    expect(page.locator('#partlast')).to_be_hidden()

    fill_equipier_page(page, 1, nom='Deux', prenom='Membre', sexe='F', year=ADULT_YEAR)
    go_next(page)
    expect(page.locator('#part3')).to_be_visible()
    expect(page.locator('#partlast')).to_be_hidden()

    fill_equipier_page(page, 2, nom='Trois', prenom='Membre', sexe='H', year=ADULT_YEAR)
    go_next(page)
    expect(page.locator('#partlast')).to_be_visible()
    expect(page.locator('#part4')).to_be_hidden()  # the 4th (unused) form must stay hidden


def test_justificatif_choice_toggles_licence_and_certificat_fields(page):
    page.goto(COURSE_PATH)
    fill_equipe_page(page, nom='Equipe Justif E2E', nombre=1)
    go_next(page)

    page.check('#id_form-0-justificatif_1')  # licence
    expect(page.locator('#id_form-0-num_licence')).to_be_visible()
    expect(page.locator('#id_form-0-piece_jointe')).to_be_visible()

    page.check('#id_form-0-justificatif_2')  # certificat médical
    expect(page.locator('#id_form-0-num_licence')).to_be_hidden()
    expect(page.locator('#id_form-0-piece_jointe')).to_be_visible()


def test_minor_equipier_requires_autorisation_field(page):
    page.goto(COURSE_PATH)
    fill_equipe_page(page, nom='Equipe Mineur E2E', nombre=1)
    go_next(page)

    fill_equipier_page(page, 0, nom='Petit', prenom='Jeune', sexe='H', year=ADULT_YEAR)
    expect(page.locator('#id_form-0-autorisation')).to_be_hidden()

    fill_equipier_page(page, 0, nom='Petit', prenom='Jeune', sexe='H', year=MINOR_YEAR)
    expect(page.locator('#id_form-0-autorisation')).to_be_visible()


def test_previous_button_returns_to_the_previous_page_with_data_kept(page):
    page.goto(COURSE_PATH)
    fill_equipe_page(page, nom='Equipe Precedent E2E', nombre=1)
    go_next(page)

    fill_equipier_page(page, 0, nom='Dupont', prenom='Jean', sexe='H', year=ADULT_YEAR, justificatif='certificat')
    go_next(page)
    expect(page.locator('#partlast')).to_be_visible()

    go_prev(page)
    expect(page.locator('#part1')).to_be_visible()
    expect(page.locator('#id_form-0-nom')).to_have_value('Dupont')
    expect(page.locator('#id_form-0-prenom')).to_have_value('Jean')

    go_prev(page)
    expect(page.locator('#part0')).to_be_visible()
    expect(page.locator('#id_nom')).to_have_value('Equipe Precedent E2E')


def test_category_list_is_filtered_by_team_size(page):
    page.goto(COURSE_PATH)
    fill_equipe_page(page, nom='Equipe Duo E2E', nombre=2)
    go_next(page)
    fill_equipier_page(page, 0, nom='Un', prenom='Membre', sexe='H', year=ADULT_YEAR)
    go_next(page)
    fill_equipier_page(page, 1, nom='Deux', prenom='Membre', sexe='F', year=ADULT_YEAR)
    go_next(page)

    radios = page.locator('#catwrapper input[type=radio]')
    expect(radios).to_have_count(1)  # only "Duo" accepts a 2-person team
    expect(page.locator('#catwrapper')).to_contain_text('Duo')


def test_duplicate_team_name_is_flagged_before_submit(page):
    register_full_team(page, nom='Equipe Doublon E2E', nombre=1, equipiers=[
        dict(nom='Dupont', prenom='Jean', sexe='H', year=ADULT_YEAR),
    ])
    expect(page).to_have_url(re.compile(r'/e2e/\d+/done/$'))

    page.goto(COURSE_PATH)
    page.locator('#id_nom').press_sequentially('Equipe Doublon E2E', delay=20)
    page.wait_for_timeout(1000)
    expect(page.locator('#nom_erreur')).to_contain_text("déjà utilisé")
