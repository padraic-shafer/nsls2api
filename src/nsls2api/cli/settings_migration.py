"""Legacy config migration for nsls2api CLI.

This module handles the one-time migration of the old bare-file config
(``~/.config/nsls2``) to the current XDG-compliant location.  It is
intentionally isolated so that it can be removed entirely — along with
``test_settings_migration.py`` — once legacy configs are no longer in
the wild.

Callers (``settings.Config.read``) interact only via the three public
functions:

- :func:`legacy_filepath` — canonical legacy path.
- :func:`migrate_legacy_config` — perform the one-time migration.
- :func:`read_legacy_fallback` — back-compat read when migration is not
  possible.
"""

import configparser
import os
import shutil
import sys
import tempfile
from pathlib import Path


def legacy_filepath() -> Path:
    """Return the old (pre-migration) config path: ``~/.config/nsls2``.

    The legacy config was written as a **bare file** (not a directory),
    which prevents other nsls2 tools from using ``~/.config/nsls2/`` as a
    directory.  This path is always ``~/.config/nsls2`` regardless of
    ``XDG_CONFIG_HOME``, because the legacy writer hard-coded it.
    """
    return Path.home() / ".config" / "nsls2"


def migrate_legacy_config(config_filepath: Path) -> Path | None:
    """Migrate the legacy bare-file config to *config_filepath*, if needed.

    If ``~/.config/nsls2`` exists as a **regular file** (the old format)
    and *config_filepath* does not yet exist, copies the content to the
    new location and removes the legacy file only after the new file is
    confirmed written.

    In the default (no-XDG) case the legacy file occupies the path
    component ``nsls2`` that must become a *directory* for the new path.
    The legacy file is removed just before ``mkdir`` so the name is free;
    content is already preserved in a temporary copy made at the start of
    migration.

    Returns the new path if migration occurred, ``None`` otherwise.

    Emits a warning to stderr and returns ``None`` (without raising) if
    migration fails for any reason, so a failure never breaks a normal CLI
    command.
    """
    legacy = legacy_filepath()
    new = config_filepath

    # Already migrated (or user already has a new-style config) — nothing to do.
    if new.exists():
        return None

    # Only migrate a plain FILE.  If legacy is a directory, skip silently.
    if not legacy.is_file():
        return None

    # Rename (the staging step) requires write+execute on the containing
    # directory, not on the file itself.
    if not os.access(legacy.parent, os.W_OK | os.X_OK):
        print(
            f"Warning: nsls2api config migration skipped — "
            f"'{legacy.parent}' is not writable. "
            f"To migrate manually:\n"
            f"  1. Move '{legacy}' aside (e.g. rename it to '{legacy}.bak')\n"
            f"  2. Create the directory '{new.parent}'\n"
            f"  3. Move the saved file into place as '{new}'",
            file=sys.stderr,
        )
        return None

    # Step 1 — copy legacy content to a temp sibling.  Legacy stays in place
    # until migration succeeds; a failure here leaves everything unchanged.
    fd, tmp_name = tempfile.mkstemp(dir=legacy.parent, prefix=".nsls2-migrate-")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        shutil.copy2(legacy, tmp)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        print(
            f"Warning: nsls2api config migration failed ({exc}). "
            f"Your settings remain at '{legacy}'. "
            f"To migrate manually:\n"
            f"  1. Move '{legacy}' aside (e.g. rename it to '{legacy}.bak')\n"
            f"  2. Create the directory '{new.parent}'\n"
            f"  3. Move the saved file into place as '{new}'",
            file=sys.stderr,
        )
        return None

    # Step 2 — move tmp to the new location, handling the name-collision case.
    #
    # When new is located under the legacy path (e.g. XDG_CONFIG_HOME unset, or
    # set to ~/.config), legacy (~/.config/nsls2, a file) sits exactly where the
    # 'nsls2' directory component of new.parent must be created.  We must remove
    # the legacy file before mkdir can succeed; since tmp already holds a full
    # copy, this is safe.
    #
    # When XDG_CONFIG_HOME points to a genuinely different directory, new lives
    # in a separate tree and there is no collision; legacy is left untouched
    # until after the new file is successfully written.
    #
    # Paths are compared after resolution so that XDG_CONFIG_HOME values that
    # refer to ~/.config via an alternative spelling (trailing slash, '..' segment,
    # or a symlink) are still recognised as the collision case.
    legacy_resolved = legacy.resolve()
    new_under_legacy = any(
        legacy_resolved == parent.resolve() for parent in new.parents
    )
    legacy_removed = False
    # Record which ancestor directories of new.parent don't yet exist so that,
    # on failure, we can undo exactly what mkdir created — and no more.  This
    # list is computed after any legacy.unlink() so the freed 'nsls2' name is
    # included when it is part of the path that must be created.
    created_dirs: list[Path] = []
    try:
        if new_under_legacy:
            legacy.unlink()           # free the 'nsls2' name; tmp holds the copy
            legacy_removed = True
        # Collect innermost-first ancestors that mkdir will create.
        p = new.parent
        while not p.exists():
            created_dirs.append(p)
            p = p.parent
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp), str(new))   # cross-device safe
    except OSError as exc:
        # Recovery: restore legacy from tmp when possible.
        if legacy_removed:
            # The legacy name was freed; mkdir may have created directory
            # entries in its place.  Remove only the empty directories we
            # created (innermost-first, rmdir only — never recursive) so
            # that the legacy name is available again for restore.
            for d in created_dirs:
                try:
                    if d.is_dir():
                        d.rmdir()
                except OSError:
                    break
            if not legacy.exists():
                # The legacy name is free — move tmp straight back.
                try:
                    shutil.move(str(tmp), str(legacy))
                    print(
                        f"Warning: nsls2api config migration failed ({exc}). "
                        f"Your settings remain at '{legacy}'. "
                        f"To migrate manually:\n"
                        f"  1. Move '{legacy}' aside (e.g. rename it to '{legacy}.bak')\n"
                        f"  2. Create the directory '{new.parent}'\n"
                        f"  3. Move the saved file into place as '{new}'",
                        file=sys.stderr,
                    )
                except OSError:
                    print(
                        f"Warning: nsls2api config migration failed ({exc}) and "
                        f"could not be recovered. "
                        f"Your settings are at '{tmp}'. "
                        f"To recover:\n"
                        f"  1. Create the directory '{new.parent}'\n"
                        f"  2. Move '{tmp}' into place as '{new}'",
                        file=sys.stderr,
                    )
            else:
                # Created dirs couldn't all be removed; legacy name still
                # occupied.  Settings safe in tmp.
                print(
                    f"Warning: nsls2api config migration failed ({exc}) and "
                    f"could not be recovered. "
                    f"Your settings are at '{tmp}'. "
                    f"To recover:\n"
                    f"  1. Create the directory '{new.parent}'\n"
                    f"  2. Move '{tmp}' into place as '{new}'",
                    file=sys.stderr,
                )
        else:
            # Legacy was not removed (XDG case, or copy step) — settings intact.
            tmp.unlink(missing_ok=True)
            print(
                f"Warning: nsls2api config migration failed ({exc}). "
                f"Your settings remain at '{legacy}'. "
                f"To migrate manually:\n"
                f"  1. Move '{legacy}' aside (e.g. rename it to '{legacy}.bak')\n"
                f"  2. Create the directory '{new.parent}'\n"
                f"  3. Move the saved file into place as '{new}'",
                file=sys.stderr,
            )
        return None

    # Step 3 — migration succeeded.
    # XDG case: legacy was not removed in step 2; delete it now.
    if not new_under_legacy:
        legacy.unlink(missing_ok=True)
    return new


def read_legacy_fallback(
    config: configparser.ConfigParser, config_filepath: Path
) -> None:
    """Populate *config* from the legacy file when *config_filepath* is absent.

    Called by ``Config.read()`` when migration was skipped or failed and
    the new config file still does not exist.  This preserves back-compat:
    existing settings (base_url, token) are not silently dropped.

    Modifies *config* in-place; returns ``None``.
    """
    legacy = legacy_filepath()
    if legacy.is_file():
        config.read(legacy)
