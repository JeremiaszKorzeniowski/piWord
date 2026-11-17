# Źródła danych i licencje

piWord nie przechowuje pełnego słownika w repozytorium. Skrypt instalacyjny
pobiera dane bezpośrednio z poniższych projektów i importuje je do lokalnej
bazy SQLite użytkownika.

## Zbiory tematyczne piWord

Plik `data/thematic_cards.csv`, lista czasowników nieregularnych oraz polskie
zbiory `SJP` i `OBCE` są krótkimi, ręcznie redagowanymi materiałami projektu
piWord. Nie są kopiami zewnętrznego słownika. Poziomy CEFR przy tych fiszkach
mają charakter orientacyjny.

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

## FreeDict Russian–Polish i Spanish–Polish

- Słowniki `rus-pol` i `spa-pol`, wydanie 2025.11.23
- Adres: <https://freedict.org/downloads/>
- Dane pochodzą z projektu FreeDict/WikDict; szczegóły autorstwa i licencji
  znajdują się w metadanych każdego pobieranego słownika.

## SMARTool — poziomy rosyjskie

- Autorzy: zespół SMARTool, UiT The Arctic University of Norway i partnerzy
- DOI: <https://doi.org/10.18710/QNAPNE>
- Repozytorium: <https://github.com/smartool/data-rus-eng>
- Licencja: Creative Commons Attribution 4.0 International

Lista obejmuje około 3000 rosyjskich leksemów na poziomach A1–B2.

## Orientacyjne poziomy hiszpańskie

- Repozytorium: <https://github.com/Talhakasikci/cefr-vocabulary-dataset>
- Zakres użycia deklarowany przez autora: projekty osobiste i edukacyjne

Jest to nieoficjalna lista społecznościowa i może zawierać błędy. piWord używa
jej wyłącznie do orientacyjnego podziału A1–B2. Nieprzypisane hasła pozostają
w grupie `OTHER`.
