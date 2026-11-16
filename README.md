# piWord

Małe urządzenie do nauki słów zbudowane z Raspberry Pi Zero W,
wyświetlacza Waveshare 2.13" V2 (250x122) i dwóch przycisków.

## Wersja 1

Pierwsza wersja obsługuje tryb `EN -> PL`:

- przycisk 1, GPIO5: pokaż tłumaczenie; ponowne naciśnięcie oznacza
  „powtórz” i przechodzi do następnej fiszki,
- przycisk 2, GPIO6: oznacz „umiem” i przejdź dalej,
- długie naciśnięcia są zarezerwowane na zmianę kierunku i trybu,
- postęp jest zapisywany lokalnie w SQLite,
- aplikacja działa bez internetu.

Konfiguracja ekranu używa standardowych linii SPI oraz niestandardowego
`RST = GPIO23`. W bibliotece Waveshare pierwsza definicja `RST_PIN` w
`waveshare_epd/epdconfig.py` musi mieć wartość `23`.

## Źródło słów

Do pierwszego uruchomienia dołączony jest niewielki zestaw testowy w
`data/seed_en_pl.csv`. Docelową bazą jest otwarty słownik FreeDict EN-PL:

- około 16 362 angielskich haseł,
- format TEI XML,
- treść na licencji GNU FDL 1.2 lub nowszej,
- aplikacja/dane źródłowe FreeDict na zasadach opisanych w repozytorium.

Repozytorium: https://github.com/freedict/fd-dictionaries/tree/master/eng-pol

Nie będziemy losować bezpośrednio ze wszystkich 16 tysięcy haseł. Importer
potrafi przyjąć listę wybranych słów, dzięki czemu później zbudujemy poziomy
np. A1, A2 i B1 zamiast pokazywać przypadkowe archaizmy.

## Uruchomienie na Raspberry Pi

Wymagane pakiety systemowe:

```bash
sudo apt install -y python3-pil python3-gpiozero python3-spidev fonts-dejavu-core
```

Repozytorium Waveshare powinno znajdować się w:

```text
/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib
```

Z katalogu projektu:

```bash
python3 -m piword run
```

Baza użytkownika powstaje w `~/.local/share/piword/piword.db`.

## Podgląd bez sprzętu

```bash
python -m piword preview --output preview.png
```

## Import FreeDict

Po pobraniu repozytorium FreeDict:

```bash
python tools/import_freedict.py \
  /sciezka/fd-dictionaries/eng-pol/letters \
  --database ~/.local/share/piword/piword.db
```

Opcjonalny plik `--word-list` powinien zawierać po jednym angielskim słowie
na linię. Bez niego importer doda wszystkie znalezione hasła.

