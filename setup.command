#!/bin/sh
set -u
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)

if [ "$#" -eq 1 ]; then
    case "$1" in
        -*) exec "$SCRIPT_DIR/scripts/install.sh" "$@" ;;
        *) exec "$SCRIPT_DIR/scripts/install.sh" "$1" --interactive ;;
    esac
elif [ "$#" -gt 1 ]; then
    exec "$SCRIPT_DIR/scripts/install.sh" "$@"
fi

cat <<'BANNER'
============================================================
 Codex Bounded Orchestrator 0.6.0
 Guided setup / macOS
============================================================
 Native roles: OpenAI GPT models only
 External APIs: optional, proposal-only, default is none
BANNER

printf '\n[ TARGET / HEDEF ]\n'
printf 'Drag the target repository folder here, then press Return:\n> '
IFS= read -r TARGET || exit 1
TARGET=$(printf '%s' "$TARGET" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//" -e 's/\\ / /g')
case "$TARGET" in
    "~/"*) TARGET="$HOME/${TARGET#~/}" ;;
esac

printf '\n[ ACTION / ISLEM ]\n'
printf '  1) Safe install/update  - back up only when replacement is chosen\n'
printf '  2) Dry run only        - preview; write nothing\n'
printf '  3) Uninstall           - remove unchanged managed files\n'
printf 'Select [1]: '
IFS= read -r ACTION || exit 1
ACTION=${ACTION:-1}

set -- "$TARGET"
case "$ACTION" in
    2) set -- "$@" --dry-run --interactive ;;
    3) set -- "$@" --uninstall ;;
    1|"")
        set -- "$@" --interactive
        printf '\n[ CONFLICTS / CAKISMALAR ]\n'
        printf 'Default keeps files that differ. Choose yes only to back up and replace them.\n'
        printf 'Replace conflicting managed role/skill/tool files? [y/N]: '
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
