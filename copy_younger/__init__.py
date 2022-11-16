"""."""

from anki.collection import OpChanges
from anki.models import NotetypeId
from anki.notes import Note, NoteId
import aqt
from aqt import mw, Collection
from aqt.browser import Browser
from aqt.operations import CollectionOp
from aqt.utils import tooltip, shortcut
from aqt.qt import QAction
import typing
from typing import List


# Copy direction: from the eldest to the youngest
names = ['Yaryna', 'Solia', 'Daryna']


PRIVATE_TAGS = ['leech'] + [t.lower() for t in names]


def get_nonprivate_tags(tags: List[str]) -> List[str]:
    """Filter out well known tags."""
    return [t for t in tags if t not in PRIVATE_TAGS]


def copy_tags_preserving_private(src: List[str],
                                 dst: List[str]) -> List[str]:
    """Copy the shared tags from src preserving the private tags from dst."""
    return sorted([t for t in dst if t in PRIVATE_TAGS] +
                  [t for t in src if t not in PRIVATE_TAGS])


def determine_child_index(card_type: str) -> int:
    """Determine child index from the card type."""
    for idx, name in enumerate(names):
        if name in card_type:
            return idx
    return -1


def copy_note(col: Collection, nid: NoteId):
    """."""
    note = col.get_note(nid)
    model = note.note_type()
    # Let's assume all the cards belong to the same deck for now
    src_deck = col.decks.get(note.cards()[0].did)
    if not src_deck or not model:
        return
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
    dst_deck_name = src_deck_name.replace(src_name, dst_name)
    dst_deck = col.decks.by_name(dst_deck_name)
    if not dst_deck:
        tooltip(f"No such deck {dst_deck_name}, adding", period=2000)
        col.decks.add_normal_deck_with_name(dst_deck_name)
        dst_deck = col.decks.by_name(dst_deck_name)

    dst_type_name = src_type.replace(src_name, dst_name)
    dst_type = col.models.by_name(dst_type_name)
    if not dst_type:
        tooltip(f"No such note type {dst_type_name}", period=2000)
        return

    col.decks.select(dst_deck['id'])

    new_note = col.new_note(dst_type)
    new_note.fields = note.fields
    new_note.tags = copy_tags_preserving_private(note.tags, [])
    print(new_note)
    col.add_note(new_note, dst_deck['id'])
    col.decks.save(dst_deck)

    note.tags.append(dst_tag)
    col.update_note(note)


def copy_for_younger(col: Collection, browser: Browser) -> OpChanges:
    """."""
    # Set checkpoint
    pos = col.add_custom_undo_entry("Copy younger")

    nids = browser.selected_notes()
    if not nids:
        tooltip("No notes selected.", period=2000)
        return col.merge_undo_entries(pos)

    for nid in nids:
        copy_note(col, nid)

    # Commit the changes
    return col.merge_undo_entries(pos)


def copy_op(*, parent: aqt.QWidget, browser: Browser) -> CollectionOp:
    return CollectionOp(parent, lambda col: copy_for_younger(col, browser))


def synchronize_child(col: Collection, child_name: str,
                      src_mid: NotetypeId, dst_mid: NotetypeId) -> List[Note]:
    """Synchronize all the notes of the model dst_mid taking data
    from the model src_mid."""
    src_type = col.models.get(src_mid)
    assert src_type
    src_type_name = src_type['name']
    dst_type = col.models.get(dst_mid)
    assert dst_type
    dst_type_name = dst_type['name']
    print(f"Synchronizing {dst_type_name}")
    notes_to_flush = []
    # Iterate over all the notes of the destination model
    for nid in col.models.nids(dst_mid):
        note = col.get_note(nid)
        # Use the field "front" as the search key to find the source note
        front_field = note.fields[0]
        query = f'note:"{src_type_name}" front:"{front_field}"'
        src_nids = col.find_notes(query)
        if len(src_nids) != 1:
            print(f"Can't find the source of {front_field}")
            continue
        # There's the source note
        src_note = col.get_note(src_nids[0])
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


def synchronize_younger(col: Collection) -> OpChanges:
    """Synchronize the notes assuming the name[0] is the master copy.

    When notes evolve, fields and tags may change. We'll iterate over
    the younger children cards and copy the fields from the master copy.
    The tags need to be carefully merged though to avoid messing with
    "leach", "solia" etc.
    """

    # Set checkpoint
    pos = col.add_custom_undo_entry("Synchronize child")
    notes_to_flush = []

    # Iterate over all the models
    for mid_name in col.models.all_names_and_ids():
        # Only English requires synchronization for now
        mname = mid_name.name
        mid = typing.cast(NotetypeId, mid_name.id)
        if "English" not in mname:
            continue
        child_index = determine_child_index(mname)
        if child_index > 0:
            child_name = names[child_index]
            src_mname = mname.replace(child_name, names[0])
            src_mid = col.models.id_for_name(src_mname)
            if not src_mid:
                continue
            notes_to_flush += synchronize_child(col, child_name, src_mid, mid)

    if notes_to_flush:
        col.update_notes(notes_to_flush)
    return col.merge_undo_entries(pos)


def sync_op(*, parent: aqt.QWidget) -> CollectionOp:
    return CollectionOp(parent, lambda col: synchronize_younger(col))


def setup_actions(browser):
    """."""
    browser.form.menu_Cards.addSeparator()
    action = QAction("Copy for younger", browser)
    action.setShortcut(shortcut("Alt+D"))
    action.triggered.connect(lambda: copy_op(parent=mw, browser=browser)
                             .success(lambda _: browser.search())
                             .run_in_background())
    browser.form.menu_Cards.addAction(action)
    action = QAction("Synchronize younger", browser)
    action.triggered.connect(lambda: sync_op(parent=mw).run_in_background())
    browser.form.menu_Cards.addAction(action)


aqt.gui_hooks.browser_menus_did_init.append(setup_actions)
