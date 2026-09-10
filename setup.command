
#!/bin/sh
set -u
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)

if [ "$#" -gt 0 ]; then
    exec "$SCRIPT_DIR/scripts/install.sh" "$@"
fi

cat <<'BANNER'
============================================================
 Codex Bounded Orchestrator 0.2.0 - macOS installer
 Astra owns | Terra maps/verifies | Sol builds/diagnoses
============================================================
BANNER

printf '\nDrag the target repository folder here, then press Return:\n> '
IFS= read -r TARGET || exit 1
TARGET=$(printf '%s' "$TARGET" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//" -e 's/\\ / /g')
case "$TARGET" in
    "~/"*) TARGET="$HOME/${TARGET#~/}" ;;
esac

printf '\nAction:\n  1) Safe install/update\n  2) Dry run only\n  3) Uninstall managed files\nSelect [1]: '
IFS= read -r ACTION || exit 1
ACTION=${ACTION:-1}

PROFILE=astra
if [ "$ACTION" != 3 ]; then
    printf '\nOwner profile:\n  1) Astra medium (recommended)\n  2) Sol high fallback\nSelect [1]: '
    IFS= read -r PROFILE_CHOICE || exit 1
    case "${PROFILE_CHOICE:-1}" in
        2) PROFILE=sol ;;
        *) PROFILE=astra ;;
    esac
fi

set -- "$TARGET" --profile "$PROFILE"
case "$ACTION" in
    2) set -- "$@" --dry-run ;;
    3) set -- "$@" --uninstall ;;
    1|"")
        printf '\nReplace conflicting managed role/skill/tool files after backup? [y/N]: '
        IFS= read -r FORCE_CHOICE || exit 1
        case "$FORCE_CHOICE" in y|Y|yes|YES|Yes) set -- "$@" --force ;; esac

        printf 'Replace an existing .codex/config.toml after backup? [y/N]: '
        IFS= read -r CONFIG_CHOICE || exit 1
        case "$CONFIG_CHOICE" in y|Y|yes|YES|Yes) set -- "$@" --force-config ;; esac
        ;;
    *)
        printf '%s\n' 'Invalid action.' >&2
        exit 2
        ;;
esac

printf '\nRunning installer...\n\n'
"$SCRIPT_DIR/scripts/install.sh" "$@"
STATUS=$?
printf '\nInstaller exited with status %s.\n' "$STATUS"
printf 'Press Return to close this window.'
IFS= read -r _ || true
exit "$STATUS"
