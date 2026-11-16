#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/piword/dictionaries"
database="${XDG_DATA_HOME:-$HOME/.local/share}/piword/piword.db"

for command_name in curl tar sha512sum python3; do
    command -v "$command_name" >/dev/null || {
        echo "Brakuje polecenia: $command_name" >&2
        exit 1
    }
done

mkdir -p "$cache_dir" "$(dirname "$database")"

download() {
    local url="$1"
    local output="$2"
    curl -fL --retry 3 -o "$output" "$url"
}

download_archive() {
    local pair="$1"
    local version="$2"
    local archive="freedict-$pair-$version.src.tar.xz"
    local base="https://download.freedict.org/dictionaries/$pair/$version"
    download "$base/$archive" "$cache_dir/$archive"
    download "$base/$archive.sha512" "$cache_dir/$archive.sha512"
    (cd "$cache_dir" && sha512sum -c "$archive.sha512")
}

echo "Pobieram słowniki FreeDict EN-PL, RU-PL i ES-PL..."
download_archive "eng-pol" "0.2.1"
download_archive "rus-pol" "2025.11.23"
download_archive "spa-pol" "2025.11.23"

download \
    "https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master/cefrj-vocabulary-profile-1.5.csv" \
    "$cache_dir/cefrj-vocabulary-profile-1.5.csv"
download \
    "https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master/octanove-vocabulary-profile-c1c2-1.0.csv" \
    "$cache_dir/octanove-vocabulary-profile-c1c2-1.0.csv"

for level in A1 A2 B1 B2; do
    download \
        "https://raw.githubusercontent.com/smartool/data-rus-eng/main/SMARTool_data_$level.csv" \
        "$cache_dir/SMARTool_data_$level.csv"
    download \
        "https://raw.githubusercontent.com/Talhakasikci/cefr-vocabulary-dataset/main/vocab_csv/es-$level.csv" \
        "$cache_dir/es-$level.csv"
done

temp_dir="$(mktemp -d -t piword-dictionaries.XXXXXX)"
service_was_active=false
cleanup() {
    if [[ -n "${temp_dir:-}" && "$temp_dir" == /tmp/piword-dictionaries.* ]]; then
        rm -rf -- "$temp_dir"
    fi
    if [[ "$service_was_active" == true ]]; then
        sudo systemctl start piword.service
    fi
}
trap cleanup EXIT

if systemctl is-active --quiet piword.service; then
    service_was_active=true
    sudo systemctl stop piword.service
fi

import_dictionary() {
    local pair="$1"
    local version="$2"
    local mode="$3"
    local language="$4"
    local source_name="$5"
    shift 5
    local archive="freedict-$pair-$version.src.tar.xz"
    local extract_dir="$temp_dir/$pair"
    mkdir -p "$extract_dir"
    tar -xJf "$cache_dir/$archive" -C "$extract_dir"

    local xml_source
    xml_source="$(find "$extract_dir" -type d -name letters -print -quit)"
    if [[ -z "$xml_source" ]]; then
        xml_source="$(find "$extract_dir" -type f -name "$pair.tei" -print -quit)"
    fi
    if [[ -z "$xml_source" ]]; then
        echo "Archiwum $pair nie zawiera oczekiwanego XML/TEI." >&2
        exit 1
    fi

    /usr/bin/python3 "$project_dir/tools/import_freedict.py" \
        "$xml_source" \
        --database "$database" \
        --mode "$mode" \
        --headword-language "$language" \
        --source-name "$source_name" \
        "$@"
}

echo "Importuję angielski..."
import_dictionary "eng-pol" "0.2.1" "en_pl" "en" "FreeDict eng-pol" \
    --cefr "$cache_dir/cefrj-vocabulary-profile-1.5.csv" \
    --cefr "$cache_dir/octanove-vocabulary-profile-c1c2-1.0.csv"

ru_levels=()
es_levels=()
for level in A1 A2 B1 B2; do
    ru_levels+=(--cefr "$cache_dir/SMARTool_data_$level.csv")
    es_levels+=(--cefr "$cache_dir/es-$level.csv")
done

echo "Importuję rosyjski..."
import_dictionary "rus-pol" "2025.11.23" "ru_pl" "ru" "FreeDict rus-pol" "${ru_levels[@]}"

echo "Importuję hiszpański..."
import_dictionary "spa-pol" "2025.11.23" "es_pl" "es" "FreeDict spa-pol" "${es_levels[@]}"

echo "Gotowe. Wszystkie słowniki są w: $database"
