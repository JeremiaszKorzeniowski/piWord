#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/piword/dictionaries"
database="${XDG_DATA_HOME:-$HOME/.local/share}/piword/piword.db"
archive="freedict-eng-pol-0.2.1.src.tar.xz"
archive_url="https://download.freedict.org/dictionaries/eng-pol/0.2.1/$archive"
checksum_url="$archive_url.sha512"
cefr_j="cefrj-vocabulary-profile-1.5.csv"
cefr_j_url="https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master/$cefr_j"
cefr_c1c2="octanove-vocabulary-profile-c1c2-1.0.csv"
cefr_c1c2_url="https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master/$cefr_c1c2"

for command_name in curl tar sha512sum python3; do
    command -v "$command_name" >/dev/null || {
        echo "Brakuje polecenia: $command_name" >&2
        exit 1
    }
done

mkdir -p "$cache_dir" "$(dirname "$database")"
echo "Pobieram FreeDict EN-PL i listy poziomów CEFR..."
curl -fL --retry 3 -o "$cache_dir/$archive" "$archive_url"
curl -fL --retry 3 -o "$cache_dir/$archive.sha512" "$checksum_url"
curl -fL --retry 3 -o "$cache_dir/$cefr_j" "$cefr_j_url"
curl -fL --retry 3 -o "$cache_dir/$cefr_c1c2" "$cefr_c1c2_url"

(
    cd "$cache_dir"
    sha512sum -c "$archive.sha512"
)

temp_dir="$(mktemp -d -t piword-dictionary.XXXXXX)"
service_was_active=false
cleanup() {
    if [[ -n "${temp_dir:-}" && "$temp_dir" == /tmp/piword-dictionary.* ]]; then
        rm -rf -- "$temp_dir"
    fi
    if [[ "$service_was_active" == true ]]; then
        sudo systemctl start piword.service
    fi
}
trap cleanup EXIT

tar -xJf "$cache_dir/$archive" -C "$temp_dir"
xml_source="$(find "$temp_dir" -type d -name letters -print -quit)"
if [[ -z "$xml_source" ]]; then
    xml_source="$(find "$temp_dir" -type f -name '*.xml' -printf '%h\n' -quit)"
fi
if [[ -z "$xml_source" ]]; then
    echo "Archiwum FreeDict nie zawiera oczekiwanych plików XML." >&2
    exit 1
fi

if systemctl is-active --quiet piword.service; then
    service_was_active=true
    sudo systemctl stop piword.service
fi

/usr/bin/python3 "$project_dir/tools/import_freedict.py" \
    "$xml_source" \
    --database "$database" \
    --cefr "$cache_dir/$cefr_j" \
    --cefr "$cache_dir/$cefr_c1c2"

echo "Gotowe. Pełny słownik jest w: $database"
