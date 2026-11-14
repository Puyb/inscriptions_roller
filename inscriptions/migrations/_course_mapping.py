"""Regroupement des editions historiques par course (revu a la main d'apres le dump
du 2026-08-04). Cle : uid de la course ; 'editions' : ancien uid -> uid d'edition.

Une edition absente de ce mapping devient sa propre course (voir _migration_course)."""

COURSES = {
    '6hdeparis': {'nom': '6 Heures de Paris', 'editions': {
        '6hdp13': '2013', '6hdp14': '2014', '6hdp15': '2015', '6hdp16': '2016',
        '6hdp17': '2017', '6hdeparis18': '2018', '6hdeparis2019': '2019',
        '6hdeparis2020': '2020', '6hdp21': '2021', '6hdp2022': '2022',
        '6hdp2023': '2023', '6hdeparis25': '2025', '6hdeparis2026': '2026'}},
    'rollenseine': {'nom': "Roll'en Seine - 6h de Mont-Saint-Aignan", 'editions': {
        '6hmsa16': '2016', '6hmsa17': '2017', '6hmsa18': '2018', '6hmsa19': '2019'}},
    'rollersday': {'nom': 'Rollers Day de Sainte-Adresse', 'editions': {
        '2hsa16': '2016', '6hstad17': '2017', '6hsta18': '2018',
        '6hstad19': '2019', '6hstad20': '2020', '6hstad21': '2021'}},
    '6hbeauvais': {'nom': '6h de Beauvais', 'editions': {
        '6hb16': '2016', '6hrb18': '2018'}},
    'rouliroula': {'nom': '6h Rouliroula (Nivelles)', 'editions': {
        '6hrr2017': '2017', '6hrr2018': '2018'}},
    'grolrace': {'nom': 'GROL Race', 'editions': {
        '24hgr18': '2018', 'gr10': '2019', 'gr10junior': '2019-junior',
        'gr2020j': '2020', 'gr2021': '2021', 'gr21jeunes': '2021-jeunes',
        'gr22': '2022', 'gr22j': '2022-jeunes', 'gr23': '2023',
        'gr236': '2023-6h', 'gr23j': '2023-3h-jeunes', 'gr23a': '2023-accompagnateurs'}},
    '6htroyes': {'nom': '6h Roller Rosières Troyes', 'editions': {
        '6htroyes18': '2018', '6htroyes19': '2019', '6htroyes20': '2020',
        '6htroyes22': '2022', '6htroyes23': '2023', '6htroyes2024': '2024',
        '6htroyes2025': '2025', '3htroyes25': '2025-3h',
        '6htroyes2026': '2026', '3htroyes2026': '2026-3h'}},
    'marathontroyes': {'nom': 'Marathon de Troyes', 'editions': {'mrtage26': '2026'}},
    '6hsudessonne': {'nom': '6h Roller Sud Essonne', 'editions': {
        '6hse18': '2018', '6hse2019': '2019', '6hse20': '2020', '6hse22': '2022'}},
    '6hamboise': {'nom': "6h du Val d'Amboise", 'editions': {
        '6h18amb': '2019', '6h20amb': '2020'}},
    'ballanmire': {'nom': 'Ballan-Miré (6h de Touraine, 3h)', 'editions': {
        '6h20trs': '2020', '3hbm22': '2022'}},
    '6hbetz': {'nom': 'Betz-le-Château', 'editions': {'6h19btz': '2019'}},
    'krollrace': {'nom': "K'Roll Race (Tremblay-en-France)", 'editions': {
        '6hkroll190519': '2019', 'smkrol19': '2019-semi',
        '6hkrr2020': '2020', 'csmkrr2020': '2020-semi',
        '6hkroll05062022': '2022', 'smkrol04062022': '2022-semi'}},
    'nivernaise': {'nom': 'La Nivernaise', 'editions': {
        '6hni23': '2024', '6hni25': '2025', '6hni26': '2026'}},
    'lafertegaucher': {'nom': 'La Ferté-Gaucher', 'editions': {
        '6hlfg': '2021', '6hlfg22': '2022', '6hlfg2023': '2023'}},
    '6hcarcassonne': {'nom': '6h de Carcassonne', 'editions': {'6hcarca23': '2023'}},
    '6htrrolls': {'nom': 'Les 6h des TRrollS (Muret)', 'editions': {'6hdestrrolls19': '2019'}},
    'tienen': {'nom': 'Mémorial Martijn Hoelbeek (Tienen)', 'editions': {
        '6ht25': '2025', '4uurmh': '2026'}},
    'randobow': {'nom': 'Rando Bow', 'editions': {'bowrp21': '2021'}},
}

# ancien uid -> (uid de course, uid d'edition)
PAR_ANCIEN_UID = {
    ancien: (course, edition)
    for course, data in COURSES.items()
    for ancien, edition in data['editions'].items()
}
