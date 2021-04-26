"""."""

import aqt
from aqt import mw
from aqt.utils import tooltip, shortcut
from aqt.qt import QAction


def copy_note(nid):
    """."""
    note = mw.col.getNote(nid)
    model = note.model()
    if model['name'] != "English Yaryna":
        word = note["Front"]
        tooltip(f"Not Yaryna's card: {word}", period=2000)
        return
    if 'solia' in note.tags:
        word = note["Front"]
        tooltip(f"Already copied: {word}", period=2000)
        return

    # Assign model to deck
    solia_deck = mw.col.decks.byName("English::Solia")
    solia_type = mw.col.models.byName("English Solia")
    mw.col.decks.select(solia_deck['id'])
    solia_deck['mid'] = solia_type['id']
    mw.col.decks.save(solia_deck)
    # Assign deck to model
    mw.col.models.setCurrent(solia_type)
    mw.col.models.current()['did'] = solia_deck['id']
    mw.col.models.save(solia_type)

    new_note = mw.col.newNote()
    new_note.fields = note.fields
    new_note.tags = note.tags
    print(new_note)
    mw.col.add_note(new_note, solia_deck['id'])

    note.tags.append('solia')
    note.flush()


def copy_for_solia(browser):
    """."""
    nids = browser.selectedNotes()
    if not nids:
        tooltip("No notes selected.", period=2000)
        return

    # Set checkpoint
    mw.progress.start()
    mw.checkpoint("Copy Notes for Solia")
    browser.model.beginReset()

    for nid in nids:
        copy_note(nid)

    # Reset collection and main window
    browser.model.endReset()
    mw.progress.finish()
    mw.col.reset()
    mw.reset()
    browser.col.save()


def setup_actions(browser):
    """."""
    action = QAction("Copy for Solia", browser)
    action.setShortcut(shortcut("Alt+D"))
    action.triggered.connect(lambda: copy_for_solia(browser))
    browser.form.menu_Cards.addSeparator()
    browser.form.menu_Cards.addAction(action)


aqt.gui_hooks.browser_menus_did_init.append(setup_actions)
