#!/usr/bin/env bash
set -euo pipefail

main() {
    script_path="$(readlink -f -- "${BASH_SOURCE[0]}")"
    project_dir="$(dirname -- "$(dirname -- "$script_path")")"

    if [[ "$(basename -- "$0")" == "xdver" ]]; then
        exec bash "$project_dir/scripts/version.sh" "$@"
    fi

    cd "$project_dir"

    mkdir -p "$HOME/.local/bin"
    ln -sfn "$project_dir/scripts/update.sh" "$HOME/.local/bin/xd"
    ln -sfn "$project_dir/scripts/update.sh" "$HOME/.local/bin/xdver"
    ln -sfn "$project_dir/scripts/db.sh" "$HOME/.local/bin/xdb"

    if [[ "$(git branch --show-current)" != "main" ]]; then
        echo "Aktualizacja wymaga galezi main."
        exit 1
    fi

    if [[ -n "$(git status --porcelain)" ]]; then
        echo "Masz lokalne zmiany. Zapisz je w Git przed aktualizacja."
        exit 1
    fi

    echo "Pobieram informacje z GitHuba..."
    git fetch origin

    if [[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]]; then
        echo "Masz juz aktualna wersje."
        exit 0
    fi

    git merge-base --is-ancestor HEAD origin/main || {
        echo "Historia lokalna rozni sie od origin/main. Potrzebne reczne sprawdzenie."
        exit 1
    }

    read -r -p "Aktualizowac piWord i zrestartowac wyswietlacz? [t/N] " answer
    [[ "$answer" == "t" || "$answer" == "T" ]] || exit 0

    git merge --ff-only origin/main
    sudo systemctl restart piword.service
    systemctl status piword.service --no-pager
}

main "$@"

