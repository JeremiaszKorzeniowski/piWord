# Źródła danych i licencje

piWord nie przechowuje pełnego słownika w repozytorium. Skrypt instalacyjny
pobiera dane bezpośrednio z poniższych projektów i importuje je do lokalnej
bazy SQLite użytkownika.

## FreeDict English–Polish

- Projekt: FreeDict, słownik `eng-pol`, wydanie 0.2.1
- Autorzy źródłowego słownika: Tadeusz Piotrowski i Zygmunt Saloni
- Adres: <https://download.freedict.org/dictionaries/eng-pol/0.2.1/>
- Licencja danych: GNU Free Documentation License 1.2 lub nowsza

## CEFR-J Vocabulary Profile

- CEFR-J Wordlist Version 1.5
- Opracowanie: Yukio Tono, Tokyo University of Foreign Studies
- Adres: <https://www.cefr-j.org/download_eng.html>
- Repozytorium z maszynowo czytelnym CSV:
  <https://github.com/openlanguageprofiles/olp-en-cefrj>

Lista służy wyłącznie do przypisania angielskich haseł do poziomów A1–B2.
Należy cytować ją zgodnie z informacją podaną przez projekt CEFR-J.

## Octanove Vocabulary Profile C1/C2

- Adres: <https://github.com/openlanguageprofiles/olp-en-cefrj>
- Licencja: Creative Commons Attribution-ShareAlike 4.0 International

Lista uzupełnia klasyfikację o poziomy C1 i C2. Hasła, których nie ma na
żadnej z list poziomów, są oznaczane jako `OTHER`.
