"""."""

import aqt
from aqt import mw
from aqt.utils import tooltip, shortcut
from aqt.qt import QAction


# Copy direction: from the eldest to the youngest
names = ['Yaryna', 'Solia', 'Daryna']


def copy_note(nid):
    """."""
    note = mw.col.getNote(nid)
    model = note.model()
    # Let's assume all the cards belong to the same deck for now
    src_deck = mw.col.decks.get(note.cards()[0].did)
    src_deck_name = src_deck["name"]

    # Source card type
    src_type = model['name']
    src_name = src_type.split()[-1]
    src_index = names.index(src_name)

    # Sanity checks
    if src_index == -1:
        word = note["Front"]
        tooltip(f"Not one of {','.join(names)}: {word}", period=2000)
        return
    if src_index > len(names) - 2:
        word = note["Front"]
        tooltip(f"Can't copy from {names[-1]}: {word}", period=2000)
        return

    # Destination card type
    dst_name = names[src_index + 1]
    dst_tag = dst_name.lower()

    if dst_tag in note.tags:
        word = note["Front"]
        tooltip(f"Already copied: {word}", period=2000)
        return

    # Assign model to deck
    dst_deck = mw.col.decks.byName(src_deck_name.replace(src_name, dst_name))
    dst_type = mw.col.models.byName(src_type.replace(src_name, dst_name))
    mw.col.decks.select(dst_deck['id'])
    dst_deck['mid'] = dst_type['id']
    mw.col.decks.save(dst_deck)
    # Assign deck to model
    mw.col.models.setCurrent(dst_type)
    mw.col.models.current()['did'] = dst_deck['id']
    mw.col.models.save(dst_type)

    new_note = mw.col.newNote()
    new_note.fields = note.fields
    new_note.tags = note.tags
    print(new_note)
    mw.col.add_note(new_note, dst_deck['id'])

    note.tags.append(dst_tag)
    note.flush()


def copy_for_younger(browser):
    """."""
    nids = browser.selectedNotes()
    if not nids:
        tooltip("No notes selected.", period=2000)
        return

    # Set checkpoint
    mw.progress.start()
    mw.checkpoint("Copy Notes for younger")
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
    action = QAction("Copy for younger", browser)
    action.setShortcut(shortcut("Alt+D"))
    action.triggered.connect(lambda: copy_for_younger(browser))
    browser.form.menu_Cards.addSeparator()
    browser.form.menu_Cards.addAction(action)


aqt.gui_hooks.browser_menus_did_init.append(setup_actions)
