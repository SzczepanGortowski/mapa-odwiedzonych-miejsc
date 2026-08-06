# Usprawnienia i roadmapa

Lista rzeczy wartych zrobienia w tym projekcie, uporządkowana według tego, co
odblokowuje co. Liczby w sekcji o wydajności pochodzą z pomiarów na tym
zbiorze (354 wizyty, Python 3.11, Windows) — reszta oznaczona jako
*przypuszczenie* to hipotezy do sprawdzenia, nie ustalenia.

Oznaczenia nakładu pracy: **S** ≈ godzina, **M** ≈ pół dnia, **L** ≈ kilka dni.

---

## Stan obecny

| | |
|---|---|
| Dane | 354 wizyty, 331 miejsc, 12 państw, 42 wpisy UNESCO w 45 miejscach |
| Kod | 1 163 linii aplikacji (`app.py` + pakiet `wycieczki`), 444 testów, 298 skryptów |
| Testy | 57 lokalnie, 56 + 1 pominięty bez prywatnych danych |
| Zależności | streamlit, folium, pandas, altair — plus `reverse_geocoder` tylko do wzbogacania |

Logika nie importuje Streamlita, więc daje się testować i przenieść do innego
interfejsu bez przepisywania.

---

## Wydajność

Pomiary z 2026-08-06, `data/pozycje.csv` (354 wiersze):

| operacja | czas | uwagi |
|---|---:|---|
| `build_map` — 354 punkty | **234–408 ms** | 653 kB HTML, przy **każdej** zmianie filtra |
| `load_dataset` (bez cache) | 58 ms | raz na zmianę pliku, `st.cache_data` |
| — w tym `_place_ids` | 59 ms | dominuje koszt wczytania |
| wykresy (6 sztuk łącznie) | ~128 ms | |
| `summarize` | 0,7 ms | pomijalne |

### Mapa to jedyne wąskie gardło

Skalowanie jest liniowe — **~0,7 ms i ~1,9 kB na punkt**, sama pusta mapa
Folium kosztuje 3 ms. Cały koszt to generowanie osobnego obiektu
`CircleMarker` z HTML-owym popupem dla każdej wizyty w
[`mapview.build_map`](src/wycieczki/mapview.py).

| punktów | czas | HTML |
|---:|---:|---:|
| 100 | 85 ms | 186 kB |
| 354 | 234 ms | 653 kB |
| 1 000 | ~700 ms *(ekstrapolacja)* | ~1,9 MB |
| 3 000 | ~2 s *(ekstrapolacja)* | ~5,6 MB |

Przy obecnym zbiorze to jest znośne — 234 ms opóźnienia po ruchu suwakiem.
Przy trzykrotnie większym zbiorze zrobi się męczące, a HTML przesyłany do
przeglądarki po każdej zmianie filtra stanie się problemem sam w sobie.

Trzy wyjścia, od najtańszego:

1. **Cache na sygnaturze filtra** (S) — opakować `build_map` w `st.cache_data`
   z kluczem `(hash danych, MapOptions)`. Powroty do wcześniejszego stanu
   filtrów stają się natychmiastowe. Nie pomaga przy pierwszym wejściu
   w dany stan.
2. **Jedna warstwa GeoJSON zamiast N markerów** (M) — `folium.GeoJson`
   ze wspólnym `style_function` i `GeoJsonPopup` generuje jeden obiekt
   zamiast 354. *Przypuszczenie: kilkukrotna redukcja HTML — do zmierzenia.*
3. **Zamiana Folium na `st.pydeck_chart`** (L) — WebGL, bez dodatkowej
   zależności (pydeck jest już w zależnościach Streamlita), radzi sobie
   z dziesiątkami tysięcy punktów. Kosztem jest przepisanie popupów, legendy
   i podkładów oraz utrata prostoty Leafletu.

Wariant 1 warto zrobić od razu, 2 i 3 dopiero gdy zbiór urośnie.

### `_place_ids` — do obserwacji, nie do naprawy

59 ms na 354 wiersze to dużo jak na tę operację; koszt siedzi w `iterrows()`
i wywołaniu `haversine_km` osobno dla każdego wiersza w
[`data._place_ids`](src/wycieczki/data.py). Wektoryzacja obcięłaby to
do jednostek milisekund (S). **Nie ma jednak po co** — funkcja działa
wewnątrz cache'owanego `load_dataset`, czyli raz na zmianę pliku CSV.
Warto wrócić, jeśli zbiór przekroczy kilka tysięcy wizyt.

---

## Dług techniczny i słabe punkty

### 1. Brak CI (S, wysoki priorytet)

Repozytorium jest na GitHubie, ale nic nie uruchamia testów. `ruff` jest
skonfigurowany w [`pyproject.toml`](pyproject.toml) i **nigdy nie został
uruchomiony** — nie jest nawet zainstalowany lokalnie. Minimalny
`.github/workflows/ci.yml` z `pytest` i `ruff check` na push i PR.

Testy działają bez prywatnych danych (na `pozycje.example.csv`), więc CI
zadziała od ręki.

### 2. Test aplikacji nie jest w repozytorium (S, wysoki priorytet)

Podczas budowy używałem skryptu opartego na `streamlit.testing.v1.AppTest`,
który przeklikuje filtry i sprawdza brak wyjątków — ale **został w katalogu
tymczasowym**. To luka: dwa realne błędy (`KeyError: 'panstwo'` po zmianie
schematu, `KeyError: 'unesco'` w wykresie państw) wyszły dopiero przy ręcznym
uruchomieniu.

Testy wykresów w [`tests/test_charts.py`](tests/test_charts.py) łapią teraz
ten drugi przypadek, ale samego `app.py` nic nie pokrywa. Do dopisania
`tests/test_app.py`: uruchomienie, każdy filtr osobno, pusty wynik.

### 3. Wzbogacanie danych trzeba pamiętać ręcznie (M)

Po dopisaniu miejsca do CSV trzeba uruchomić
[`scripts/enrich_places.py`](scripts/enrich_places.py), inaczej państwo jest
„nieznane". Aplikacja o tym przypomina, ale to i tak krok do zapomnienia.

Lepiej: wykrywać przy wczytaniu wiersze bez `panstwo` i uzupełniać je
w locie, jeśli `reverse_geocoder` jest zainstalowany. UNESCO zostaje ręczne —
i słusznie, bo to decyzja, nie obliczenie.

### 4. Restart po zmianie schematu danych (S)

Streamlit nie przeładowuje modułów pakietu `wycieczki` po zmianie kolumn
w CSV — cache zwraca ramkę w starym kształcie i aplikacja wywala się na
`KeyError`. Trafiłem na to dwa razy podczas budowy; obejściem jest restart.

Naprawa: po wczytaniu sprawdzić, czy ramka ma komplet kolumn, a jeśli nie —
`st.cache_data.clear()` i ponowne wczytanie zamiast wyjątku.

### 5. Klucz UNESCO oparty na nazwie (S)

`UNESCO_SITES` w [`enrich_places.py`](scripts/enrich_places.py) jest
indeksowany przez `(nazwa, kod kraju)`. Poprawienie literówki w nazwie
miejsca po cichu gubi przypisanie do obiektu. Skrypt ostrzega o wpisach,
które nie pasują do żadnego miejsca, więc problem jest wykrywalny — ale
tylko jeśli ktoś czyta wyjście skryptu. Warto ostrzeżenie podnieść do błędu
z flagą `--allow-unused`.

### 6. Drobiazgi

- `Summary.span_km` liczy się przy każdym renderze, ale nie ma już kafelka
  KPI, który by go pokazywał — martwe pole do usunięcia albo do przywrócenia
  jako karta (S).
- Interfejs jest po polsku na sztywno; wydzielenie tekstów byłoby potrzebne
  tylko przy realnej potrzebie drugiego języka (M) — **nie warto na zapas**.
- `st_folium` jest wywoływane z `returned_objects=[]`, żeby uniknąć
  przeładowań. Świadomy kompromis: kosztem jest brak reakcji na kliknięcie
  markera (patrz Etap 3).

---

## Roadmapa

### Etap 1 — Higiena (S, ~pół dnia łącznie)

Tanie rzeczy, które zabezpieczają wszystko, co przyjdzie później.

- [ ] CI na GitHub Actions: `pytest` + `ruff check` (dług #1)
- [ ] Uruchomić `ruff` po raz pierwszy i posprzątać, co znajdzie
- [ ] `tests/test_app.py` na `AppTest` (dług #2)
- [ ] Cache `build_map` na sygnaturze filtra (wydajność, wariant 1)
- [ ] Samouzdrawiający cache przy zmianie schematu (dług #4)

### Etap 2 — Model danych (M/L)

**To jest etap, który odblokowuje najwięcej.** Dwa braki w danych ograniczają
wszystko, co dałoby się policzyć.

- [ ] **Data zamiast samego roku** (M). Kolumna `rok` niesie najmniej
      informacji ze wszystkich. Z pełną datą dostajemy: sezonowość, długość
      wyjazdów, oś czasu zamiast słupków rocznych, poprawne sortowanie
      punktów trasy. Migracja jest łagodna — `rok` da się wyliczyć z daty,
      a brakujące daty mogą zostać rocznymi.
- [ ] **Pojęcie wyjazdu** (M). Kolumna `kolor` jest reliktem po R: kolory
      oznaczały kolejne wyjazdy, ale były używane cyklicznie, więc dziś nie
      da się z nich odtworzyć podziału (2016 to 51 punktów w jednym kolorze
      z kilku różnych wyjazdów). Jawny identyfikator wyjazdu daje:
  - poprawny dystans — obecny szacunek w
    [`metrics.route_distance_by_year`](src/wycieczki/metrics.py) sumuje
    odcinki w kolejności `lp` w obrębie roku, więc skacze między
    niepowiązanymi wyjazdami i **zawyża wynik** dla lat z kilkoma podróżami;
  - filtrowanie i statystyki per wyjazd zamiast per rok;
  - sensowne rysowanie tras na mapie.
  - Przy dostępnych datach wyjazdy da się w dużej mierze wykryć
    automatycznie (przerwa > N dni), z ręczną korektą.
- [ ] Walidacja duplikatów przy wczytaniu (S). Podczas migracji odpadły
      4 pary identycznych wpisów; nowe mogą się wkraść niezauważone.

### Etap 3 — Wygoda pracy z danymi (M)

- [ ] **Formularz „dodaj miejsce"** w aplikacji (M) — nazwa, data, wklejone
      współrzędne z Map Google, dopisanie do CSV. Dziś jedyną drogą jest
      ręczna edycja pliku, co przy każdym wyjeździe jest realnym tarciem.
- [ ] Geokodowanie po nazwie (M) — wpisujesz „Bassano del Grappa", dostajesz
      współrzędne. Wymaga zewnętrznego API (Nominatim) i przemyślenia limitów
      zapytań; alternatywa offline to wyszukiwanie w bazie geonames, którą
      `reverse_geocoder` już ma na dysku.
- [ ] Kliknięcie markera pokazuje szczegóły w panelu bocznym (S) — wymaga
      zdjęcia `returned_objects=[]` i obsłużenia dodatkowego przeładowania.

### Etap 4 — Treść (M)

- [ ] **Zdjęcia** (M/L). Wspominałeś, że rozstrzygasz wątpliwości po
      zdjęciach — powiązanie folderu ze zdjęciami z miejscami byłoby
      naturalnym rozszerzeniem. Zdjęcia z aparatu i telefonu mają w EXIF
      współrzędne i datę, więc dopasowanie może być automatyczne. To
      jednocześnie źródło danych: **EXIF rozwiązałby brak dat z Etapu 2**.
- [ ] Numery i lata wpisów UNESCO (S) — dodanie identyfikatora obiektu na
      liście światowego dziedzictwa pozwoli linkować do `whc.unesco.org`
      i pokazać rok wpisania.
- [ ] Notatki do miejsc (S) — kolumna z krótkim opisem, widoczna w popupie.

### Etap 5 — Dystrybucja (M)

Do przemyślenia dopiero, gdy aplikacja ma być dostępna spoza tego komputera.

- [ ] Rozstrzygnąć konflikt: prywatne dane vs publiczne repozytorium.
      Opcje: wdrożenie z prywatnego repo (Streamlit Cloud to obsługuje),
      trzymanie CSV w prywatnym giście pobieranym przez `st.secrets`, albo
      świadome upublicznienie danych.
- [ ] Docker (S) — jeśli wdrożenie ma iść gdzieś indziej niż Streamlit Cloud.
- [ ] Hasło do aplikacji (S) — `st.secrets` plus prosta bramka, jeśli dane
      mają zostać prywatne przy publicznym adresie.

---

## Czego świadomie nie robić

Rzeczy, które wyglądają na usprawnienia, ale przy tej skali są kosztem bez
zwrotu:

- **Baza danych zamiast CSV.** 354 wiersze. CSV otwiera się w Excelu, wersjonuje
  w gicie i nie wymaga niczego stawiać. Wracać do tematu przy dziesiątkach
  tysięcy wierszy albo przy wielu użytkownikach.
- **Wektoryzacja `_place_ids`.** Działa raz na zmianę pliku (patrz wyżej).
- **Warstwa API / rozdzielenie backendu.** Jeden użytkownik, jedna maszyna.
- **Tłumaczenie interfejsu.** Dopóki nie ma drugiego odbiorcy.
