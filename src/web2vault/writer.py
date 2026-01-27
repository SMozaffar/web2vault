"""Write NoteBundle to the vault filesystem."""

from pathlib import Path

from .formatter import format_note
from .models import NoteBundle
from .utils import sanitize_filename


def write_bundle(bundle: NoteBundle, vault_path: Path) -> Path:
    """Write all notes in a bundle to a subfolder in the vault.

    Returns the path to the created subfolder.
    """
    folder_name = sanitize_filename(bundle.folder_name)
    output_dir = vault_path / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)

    for note in bundle.notes:
        filename = sanitize_filename(note.filename) + ".md"
        content = format_note(
            note,
            source_url=bundle.source_url,
            folder_name=bundle.folder_name,
            created=bundle.created_at,
        )
        filepath = output_dir / filename
        filepath.write_text(content, encoding="utf-8")

    return output_dir
