# 🗺️ Mapa wycieczek

Interaktywna mapa miejsc odwiedzonych w latach 2011–2026, zbudowana w Pythonie
i Streamlicie. Projekt zastępuje wcześniejszą wersję w R (`leaflet` + R Markdown
+ Shiny), z której przeniesiono dane — kod R nie jest już częścią repozytorium.

## Co potrafi

- **Mapa** — 354 wizyty na mapie Leaflet, punkty kolorowane rokiem (gradient
  chronologiczny) albo grupą przeniesioną z oryginalnego pliku CSV. Miejsca
  z obiektem UNESCO mają złotą obwódkę. Do wyboru trzy podkłady, klastrowanie
  punktów, mapa cieplna i linie tras.
- **Filtry** — zakres lat, państwo, wyszukiwanie po nazwie, ukrywanie powrotów,
  tylko miejsca z UNESCO.
- **Statystyki** — 331 miejsc w 12 państwach, w tym **42 wpisy z Listy
  światowego dziedzictwa UNESCO** odwiedzone w **45 miejscach**. Wizyty rok po
  roku z podziałem na nowe miejsca i powroty, narastająca liczba unikalnych
  miejsc, szacunkowy dystans, ranking miejsc odwiedzanych wielokrotnie,
  rozbicie na państwa, dziedzictwo UNESCO w dwóch ujęciach (wpisy / miejsca)
  i punkty skrajne.
- **Dane** — przeglądarka tabeli z eksportem widocznego wycinka do CSV.

Plany rozwoju, pomiary wydajności i znany dług techniczny opisuje
[IMPROVEMENTS.md](IMPROVEMENTS.md).

## Szybki start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1      # Windows;  na Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy data\pozycje.example.csv data\pozycje.csv    # Linux/macOS: cp
streamlit run app.py
```

Aplikacja otworzy się pod adresem <http://localhost:8501>. Zatrzymanie: `Ctrl+C`.

Bez `data/pozycje.csv` aplikacja nie kończy się błędem — sięga po
`data/pozycje.example.csv` i zapowiada u góry, że pokazuje dane przykładowe.
Dzięki temu uruchamia się także tam, gdzie prywatnych danych nie ma
(np. Streamlit Community Cloud).

Jeśli pakiety są zainstalowane globalnie (bez virtualenva), polecenie `streamlit`
może nie być na `PATH` — wtedy uruchom:

```powershell
python -m streamlit run app.py
```

## Struktura projektu

```
├── app.py                      # warstwa UI: układ strony, filtry, zakładki
├── src/wycieczki/
│   ├── config.py               # ścieżki, paleta, lista podkładów mapy
│   ├── data.py                 # wczytywanie i czyszczenie CSV
│   ├── geo.py                  # haversine
│   ├── metrics.py              # statystyki
│   ├── charts.py               # wykresy Altair
│   ├── mapview.py              # budowa mapy Folium
│   └── palette.py              # gradient lat, kolory grup
├── data/
│   ├── pozycje.csv             # jedyne źródło danych (poza repozytorium)
│   └── pozycje.example.csv     # 13 wizyt pokazujących format i przypadki brzegowe
├── scripts/
│   ├── migrate_from_r.py       # jednorazowa migracja danych z projektu R
│   └── enrich_places.py        # dopisuje państwo i UNESCO do CSV
└── tests/                      # pytest
```

Logika siedzi w pakiecie `wycieczki` i nie zna Streamlita — dzięki temu da się
ją testować bez uruchamiania aplikacji, a `app.py` zajmuje się wyłącznie UI.

## Dane

Prywatna historia wyjazdów (`data/pozycje.csv`) **nie jest częścią
repozytorium** — to 350+ punktów z datami rocznymi, czyli szczegółowy zapis
przemieszczeń. W repo leży `data/pozycje.example.csv` z 13 wizytami: pokazuje
format i wszystkie przypadki brzegowe, które kod obsługuje (dwie różne
Wenecje, wpis UNESCO dzielony przez Wieliczkę i Bochnię, Padwa z dwoma
wpisami, powrót do Torunia). Skopiuj go na `data/pozycje.csv` i dopisuj swoje
miejsca.

Format — separator `;`, kodowanie UTF-8 z BOM (Excel PL otwiera go
dwuklikiem bez kreatora importu):

| kolumna         | znaczenie                                          |
|-----------------|----------------------------------------------------|
| `lp`            | numer porządkowy; wyznacza kolejność punktów trasy |
| `rok`           | rok wizyty                                         |
| `lat`           | szerokość geograficzna (w wersji R: kolumna `X`)   |
| `lon`           | długość geograficzna (w wersji R: kolumna `Y`)     |
| `nazwa`         | nazwa miejsca (w wersji R: `Opis`)                 |
| `kolor`         | grupa/wyjazd — nazwa koloru markera z wersji R     |
| `panstwo`       | państwo wyznaczone ze współrzędnych                |
| `unesco`        | `tak` / `nie` — czy w miejscu jest obiekt UNESCO   |
| `unesco_obiekt` | nazwy wpisów rozdzielone ` \| `, puste gdy `nie`   |

Trzy ostatnie kolumny wypełnia `scripts/enrich_places.py` (patrz niżej). Plik
bez nich też się wczyta — państwo będzie wtedy „nieznane", a aplikacja
przypomni w zakładce **Dane**, żeby uruchomić skrypt.

### Dopisywanie nowych miejsc

Dopisz wiersz na końcu pliku i zapisz — Streamlit wykryje zmianę i przeładuje
dane. Współrzędne można wkleić prosto z Map Google; parser radzi sobie z
przecinkiem dziesiętnym i twardą spacją, która lubi się przykleić przy
kopiowaniu. Wiersze bez nazwy, roku lub współrzędnych są pomijane, a informacja
o nich pojawia się w zakładce **Dane**.

Kolumny `panstwo` i `unesco` można wpisać ręcznie albo uzupełnić skryptem:

```powershell
pip install reverse_geocoder
python scripts/enrich_places.py
```

Skrypt nadpisuje te trzy kolumny w całym pliku, więc po jego uruchomieniu
zrestartuj aplikację (`Ctrl+C` i ponownie `streamlit run app.py`) — Streamlit
nie zawsze przeładowuje moduły po zmianie schematu danych.

### Skąd się biorą państwo i UNESCO

**Państwo** wyznacza offline pakiet `reverse_geocoder` na podstawie
współrzędnych, więc nie zależy od zapisu nazwy. Jeden punkt wymagał ręcznej
korekty (Grödig — najbliższa miejscowość w bazie leży po bawarskiej stronie
granicy); poprawki trzyma słownik `COUNTRY_OVERRIDES` w skrypcie. Gibraltar
i Watykan liczone są osobno, choć Gibraltar nie jest państwem, tylko
brytyjskim terytorium zamorskim.

**UNESCO** to lista kuratorowana ręcznie w słowniku `UNESCO_SITES` — nie ma
darmowego API, które by to zrobiło za nas. Kryterium jest wąskie: wyłącznie
obiekty wpisane na **Listę światowego dziedzictwa**. Poza listą zostają
dziedzictwo niematerialne (np. dywany kwiatowe w Spycimierzu) oraz lista
informacyjna (m.in. Jasna Góra, Kazimierz Dolny, Gdańsk, Biskupin, Frombork).
Jeśli coś jest błędnie oznaczone, popraw słownik i puść skrypt jeszcze raz —
skrypt ostrzega o wpisach, które nie pasują do żadnego miejsca w danych.

Uwaga o Łuku Struvego: Litwa ma 18 punktów tego łuku, ale na Listę wpisano
tylko trzy — Gireišiai, Meškonys i Paliepiukai. W danych jest **Meškonys**,
czyli jeden z wpisanych. Punkt na wzgórzu Majokas pod Molėtai, choć należy do
łuku, na Liście nie figuruje.

### Miejsca a wpisy na Liście

To nie jest ta sama liczba i aplikacja pokazuje obie. Jeden wpis potrafi
obejmować kilka miejsc, a jedno miejsce mieć kilka wpisów:

| wpis obejmuje kilka miejsc                          | miejsce ma kilka wpisów                    |
|-----------------------------------------------------|--------------------------------------------|
| Królewskie Kopalnie Soli w Wieliczce **i Bochni**   | Padwa — ogród botaniczny **i** *urbs picta* |
| Kościoły Pokoju w Jaworze **i Świdnicy**            |                                             |
| Park Mużakowski — Łęknica **i** Bad Muskau (PL/DE)  |                                             |
| Wzgórza Prosecco — Conegliano **i** Valdobbiadene   |                                             |

Stąd **42 wpisy** w **45 miejscach**. W CSV kilka wpisów w jednym miejscu
zapisujemy w jednej komórce, rozdzielone ` | `. Wpisy wspólne dla kilku miejsc
muszą mieć **dokładnie tę samą nazwę** w każdym z nich — po niej liczone są
unikalne wpisy. Wpis transgraniczny (Park Mużakowski) liczy się w statystyce
obu państw.

## Migracja z R

Stare pliki `Pozycje — kopia*.csv` były w Windows-1250, z czterema pustymi
kolumnami na końcu i twardymi spacjami w dwóch współrzędnych. Skrypt migracyjny
scala oba pliki, czyści je i zapisuje kanoniczny CSV:

```bash
python scripts/migrate_from_r.py --source <katalog ze starymi CSV>
```

Nie trzeba go już uruchamiać — `data/pozycje.csv` jest wynikiem tej migracji
(a następnie `scripts/enrich_places.py`). Skrypt został w repozytorium jako
dokumentacja tego, skąd wzięły się dane; same pliki źródłowe z ery R nie są
częścią repozytorium.
Z 358 wierszy w nowszym pliku zostały 354 wizyty: usunięto jeden pusty wiersz na
końcu oraz cztery pary wpisów identycznych co do miejsca, roku i współrzędnych
(Gdańsk i Kruszwica 2016, Toruń i Warszawa 2017).

### Czym różni się od wersji w R

| wersja R                                        | wersja Python                                    |
|-------------------------------------------------|--------------------------------------------------|
| ścieżka na sztywno `D:\Projekty\R\Wycieczki\`   | ścieżki względne, projekt działa po skopiowaniu   |
| aplikacja Shiny nie uruchamiała się (literówka `2019s` w `ui.R`) | filtry działają, pokrycie testami |
| filtr lat liczony, ale odrzucany — mapa zawsze pokazywała komplet punktów | filtry realnie zawężają dane na mapie i w statystykach |
| CSV wczytywany trzykrotnie przy każdej zmianie suwaka | jedno wczytanie z `st.cache_data` |
| błędne współrzędne trafiały na mapę jako `NA`   | walidacja zakresów + komunikat o pominiętych wierszach |
| tylko mapa                                       | mapa, statystyki, tabela z eksportem              |
| brak informacji o państwie i UNESCO             | kolumny `panstwo`, `unesco`, `unesco_obiekt`      |

### Tożsamość miejsca

Miejsca rozpoznajemy po nazwie **i** położeniu, a nie po samej nazwie. W danych
są dwie Wenecje (pod Żninem i we Włoszech) oraz dwa Zagórowy — bez tego
liczyłyby się jako powroty do tego samego miejsca. Odwrotny przypadek też
występuje: Gdańsk, Toruń czy Frombork mają po dwa nieco różne zapisy
współrzędnych i muszą pozostać jednym miejscem. Punkty o tej samej nazwie
bliżej niż 25 km traktujemy więc jako to samo miejsce, dalsze — jako różne
(drugie dostaje sufiks `#2`).

## Testy

```bash
pip install -e ".[dev]"
pytest
```

Testy pilnują reguł czyszczenia danych (twarde spacje, przecinek dziesiętny,
współrzędne poza zakresem, brakujące kolumny), poprawności statystyk oraz tego,
że wszystkie wykresy i warianty mapy dają się zbudować — literówka w
specyfikacji Vega-Lite inaczej wychodzi dopiero w przeglądarce.

Bez `data/pozycje.csv` testy działają na pliku przykładowym; kilka testów
sprawdzających kompletność prywatnego zbioru jest wtedy pomijanych.

## Publikacja

Od strony konfiguracji repozytorium jest gotowe pod
[Streamlit Community Cloud](https://share.streamlit.io) — wystarczy wskazać
`app.py` jako plik główny, `requirements.txt` i `.streamlit/config.toml`
zostaną wykryte automatycznie.

Jest jednak haczyk: `data/pozycje.csv` nie jest w repozytorium, więc wdrożona
w ten sposób aplikacja pokaże **13 przykładowych wizyt**, a nie prawdziwe dane.
Możliwości omawia [IMPROVEMENTS.md](IMPROVEMENTS.md#etap-5--dystrybucja-m).
