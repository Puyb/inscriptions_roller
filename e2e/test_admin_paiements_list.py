"""Payment list: `custom_admin/paiements.js` appends the totals of the whole
(filtered) list to the "montant" column headers."""
import re

from playwright.sync_api import expect

TOTAL = re.compile(r'\(\d+(\.\d+)? €\)')


def test_totals_are_appended_to_column_headers(admin_page):
    admin_page.goto('/course/inscriptions/paiement/')
    expect(admin_page.locator('th.column-montant')).to_contain_text(TOTAL)
    expect(admin_page.locator('th.column-montant_frais2')).to_contain_text(TOTAL)


def test_totals_follow_the_active_filter(admin_page):
    admin_page.goto('/course/inscriptions/paiement/')
    expect(admin_page.locator('th.column-montant')).to_contain_text(TOTAL)

    # only the seeded 20 EUR cheque matches (an empty list renders no header)
    admin_page.goto('/course/inscriptions/paiement/?type=ch%C3%A8que')
    expect(admin_page.locator('th.column-montant')).to_contain_text('(20.00 €)')
