"""."""

import aqt
from aqt import mw
from aqt.operations import CollectionOp
from aqt.utils import tooltip, shortcut
from aqt.qt import QAction


# Copy direction: from the eldest to the youngest
names = ['Yaryna', 'Solia', 'Daryna']


PRIVATE_TAGS = ['leech'] + [t.lower() for t in names]


def get_nonprivate_tags(tags):
    """Filter out well known tags."""
    return [t for t in tags if t not in PRIVATE_TAGS]


def copy_tags_preserving_private(src, dst):
    """Copy the shared tags from src preserving the private tags from dst."""
    return sorted([t for t in dst if t in PRIVATE_TAGS] +
                  [t for t in src if t not in PRIVATE_TAGS])


def determine_child_index(card_type):
    """Determine child index from the card type."""
    for idx, name in enumerate(names):
        if name in card_type:
            return idx
    return -1


def copy_note(nid):
    """."""
    note = mw.col.getNote(nid)
    model = note.model()
    # Let's assume all the cards belong to the same deck for now
    src_deck = mw.col.decks.get(note.cards()[0].did)
    src_deck_name = src_deck["name"]

    # Source card type
    src_type = model['name']
    src_index = determine_child_index(src_type)

    # Sanity checks
    if src_index == -1:
        word = note["Front"]
        tooltip(f"Not one of {','.join(names)}: {word}", period=2000)
        return
    if src_index > len(names) - 2:
        word = note["Front"]
        tooltip(f"Can't copy from {names[-1]}: {word}", period=2000)
        return

    src_name = names[src_index]

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
    new_note.tags = copy_tags_preserving_private(note.tags, [])
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


def synchronize_child(col, child_name, src_mid, dst_mid):
    """Synchronize all the notes of the model dst_mid taking data
    from the model src_mid."""
    src_type_name = col.models.get(src_mid)['name']
    dst_type_name = col.models.get(dst_mid)['name']
    print(f"Synchronizing {dst_type_name}")
    notes_to_flush = []
    # Iterate over all the notes of the destination model
    for nid in col.models.nids(dst_mid):
        note = col.getNote(nid)
        # Use the field "front" as the search key to find the source note
        front_field = note.fields[0]
        query = f'note:"{src_type_name}" front:"{front_field}"'
        src_nids = col.find_notes(query)
        if len(src_nids) != 1:
            print(f"Can't find the source of {front_field}")
            continue
        # There's the source note
        src_note = col.getNote(src_nids[0])
        changed = False
        # Just overwrite the fields if different
        if src_note.fields != note.fields:
            print(f"Synchronize fields {src_note.fields} -> {note.fields}")
            note.fields = src_note.fields
            changed = True
        # Tags need to be merged carefully to avoid propagation of private
        # information like 'leech'.
        src_tags = get_nonprivate_tags(src_note.tags)
        dst_tags = get_nonprivate_tags(note.tags)
        if src_tags != dst_tags:
            old_note_tags = note.tags
            note.tags = copy_tags_preserving_private(src_note.tags, note.tags)
            changed = True
            print(f"Synchronize tags for {front_field}:"
                  + f" {src_note.tags} -> {old_note_tags} = {note.tags}")
        # Commit finally
        if changed:
            notes_to_flush.append(note)
    return notes_to_flush


def synchronize_younger(col):
    """Synchronize the notes assuming the name[0] is the master copy.

    When notes evolve, fields and tags may change. We'll iterate over
    the younger children cards and copy the fields from the master copy.
    The tags need to be carefully merged though to avoid messing with
    "leach", "solia" etc.
    """

    # Set checkpoint
    pos = col.add_custom_undo_entry("synchronize child")
    notes_to_flush = []

    # Iterate over all the models
    for mid_name in col.models.all_names_and_ids():
        # Only English requires synchronization for now
        mname = mid_name.name
        if "English" not in mname:
            continue
        child_index = determine_child_index(mname)
        if child_index > 0:
            child_name = names[child_index]
            src_mname = mname.replace(child_name, names[0])
            src_mid = col.models.id_for_name(src_mname)
            notes_to_flush += synchronize_child(col, child_name, src_mid,
                                                mid_name.id)

    if notes_to_flush:
        col.update_notes(notes_to_flush)
    return col.merge_undo_entries(pos)


def sync_op(*, parent: aqt.QWidget):
    return CollectionOp(parent, lambda col: synchronize_younger(col))


def setup_actions(browser):
    """."""
    action = QAction("Copy for younger", browser)
    action.setShortcut(shortcut("Alt+D"))
    action.triggered.connect(lambda: copy_for_younger(browser))
    browser.form.menu_Cards.addSeparator()
    browser.form.menu_Cards.addAction(action)
    action = QAction("Synchronize younger", browser)
    action.triggered.connect(lambda: sync_op(parent=mw).run_in_background())
    browser.form.menu_Cards.addAction(action)


aqt.gui_hooks.browser_menus_did_init.append(setup_actions)
