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

Czasowniki nieregularne pokazują na przedniej stronie wszystkie trzy formy,
np. `go`, a pod nim `went - gone`. Przycisk 1 odsłania polskie tłumaczenie.
Lista startowa znajduje się w `data/irregular_verbs_en_pl.csv` i jest
automatycznie dołączana także do już istniejącej bazy SQLite.

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

Importer przypisuje poziomy A1–B2 na podstawie CEFR-J Vocabulary Profile,
a C1–C2 z listy Octanove. Słowa, których nie ma na tych listach, trafiają do
grupy `OTHER` — poziom nie jest zgadywany. Szczegóły źródeł i licencji są w
`ATTRIBUTION.md`.

## Uruchomienie na Raspberry Pi

Wymagane pakiety systemowe:

```bash
sudo apt install -y python3-pil python3-gpiozero python3-spidev fonts-dejavu-core
```

Aplikacja korzysta z DejaVu Sans, a jeśli pakiet fontów nie jest dostępny,
próbuje użyć `Font.ttc` z oficjalnego repozytorium Waveshare. Brak obu fontów
nie powoduje pętli restartów usługi — uruchamiany jest awaryjny font Pillow.

Repozytorium Waveshare powinno znajdować się w:

```text
/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib
```

Z katalogu projektu:

```bash
python3 -m piword run
```

Baza użytkownika powstaje w `~/.local/share/piword/piword.db`.

## Usługa i autostart

Po ręcznym sprawdzeniu ekranu i przycisków zainstaluj usługę:

```bash
bash scripts/install-service.sh
sudo systemctl start piword.service
systemctl status piword.service --no-pager
```

Instalator uruchamiaj jako zwykły użytkownik, bez `sudo`. Sam poprosi o
uprawnienia wyłącznie przy instalacji jednostki systemd. Ustawia autostart oraz
dowiązania `~/.local/bin/xd` i `~/.local/bin/xdver`.

## Aktualizacja przez SSH

```bash
xd
```

Skrypt wymaga czystej gałęzi `main`, wykonuje `git fetch`, akceptuje wyłącznie
aktualizację fast-forward i przed zmianą pyta o potwierdzenie. Po aktualizacji
restartuje `piword.service` i pokazuje jej stan. Nie nadpisuje lokalnych zmian,
nie aktualizuje w tle i nie zmienia konfiguracji sprzętu.

Jeżeli powłoka nie znajduje polecenia `xd`, uruchom:

```bash
~/.local/bin/xd
```

Informacje o zainstalowanej wersji, commicie i usłudze pokazuje działająca
offline komenda:

```bash
xdver
```

## Podgląd bez sprzętu

```bash
python -m piword preview --output preview.png
```

## Pełny słownik i poziomy CEFR

Karta 32 GB ma bardzo duży zapas: archiwum FreeDict ma mniej niż 1 MB, a po
imporcie baza SQLite nadal zajmuje tylko niewielką część karty. Po aktualizacji
programu przez `xd` uruchom jednorazowo:

```bash
bash ~/piWord/scripts/install-dictionary.sh
```

Skrypt pobiera pełny FreeDict EN–PL, sprawdza sumę SHA-512, pobiera listy
poziomów i importuje wszystko do `~/.local/share/piword/piword.db`. Na czas
importu zatrzymuje usługę `piword.service`, a po zakończeniu uruchamia ją
ponownie. Na końcu wypisuje liczbę haseł w A1, A2, B1, B2, C1, C2 i `OTHER`.

Poziom rozpoznanej fiszki jest pokazany w nagłówku ekranu. Wybieranie jednej
grupy poziomów przyciskami dodamy razem z menu trybów; baza już przechowuje
grupy osobno i potrafi losować tylko ze wskazanego poziomu.

## Ręczny import FreeDict

Po pobraniu repozytorium FreeDict:

```bash
python tools/import_freedict.py \
  /sciezka/fd-dictionaries/eng-pol/letters \
  --database ~/.local/share/piword/piword.db \
  --cefr /sciezka/cefrj-vocabulary-profile-1.5.csv \
  --cefr /sciezka/octanove-vocabulary-profile-c1c2-1.0.csv
```

Opcjonalny plik `--word-list` powinien zawierać po jednym angielskim słowie
na linię. Bez niego importer doda wszystkie znalezione hasła.

