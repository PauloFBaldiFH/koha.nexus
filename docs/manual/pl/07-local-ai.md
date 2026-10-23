# 7. Lokalna AI

[Spis treści](README.md)

**AI**, `a`: dostawca, Ollama, zdjęcia MARC Replace i asystent staff. Konfiguracja nie instaluje narzędzi automatycznie.

## Lokalna obsługa

Czytaj ostrzeżenie CPU/RAM: może spowolnić Koha. **Ollama on this server > Check Ollama**, w razie braku **Install Ollama**. Wybór/**Download** wymaga sieci/dysku. Nazw modeli nie utrwalamy, oferta się zmienia. **Local Ollama**, URL (domyślnie `http://127.0.0.1:11434`), **Use for chat/Use for cataloguing**. Zdjęcia wymagają widzenia, sam tekst nie wystarczy. **Test connection/Save**, **F5/Ctrl+S**; wypełnienie nie zapisuje. Pusty czat używa wyboru widzenia. **Load models** odpytuje dostawcę, sygnalizuje listę wbudowaną przy awarii.

Zainstalowane zajmuje dysk, załadowane RAM. **Free memory** zwalnia bez usunięcia pobranego, później może załadować. Sekcja Ollama widoczna z innym dostawcą: sprawdź zapisane URL/dostawcę, nie zakładaj lokalności przez samą instalację.

## Narzędzia

Zainstaluj/aktualizuj MARC Replace; instalator sprawdza kompilację/skrót staff. Jeden rekord: `.mrc/.xml` lub tekst, `biblionumber`, **Preview**, porównaj/potwierdź. Puste tworzy nowy: unikaj duplikatu. Egzemplarze zachowane, wejściowe pola egzemplarzy pomijane. Poprzedni MARCXML do pobrania/ponownego wysłania z tym samym ID, nie zastępuje całego backup.

**AI cataloguing**: czytelne zdjęcia okładki/strony tytułowej/odwrotu, JPEG/PNG/WebP, przynajmniej jedno. Framework lub rekord docelowy, **Read the photos**, poczekaj i porównaj tytuł/odpowiedzialność/wydanie/ISBN/klasyfikację/braki. Popraw MARC przed zapisem, klasyfikację sprawdź w tablicach; cyfra ISBN nie dowodzi edycji. Szkic nie zapisuje pól egzemplarzy.

**Install, update or remove the assistant** zastępuje blok aktualności startu staff, bez OPAC. Wyszukiwanie Koha i ustalone odczyty zamiast dowolnego SQL. **Propozycja to nie wykonana zmiana:** sprawdź rekord/przed-po/skutek, **Approve & Execute** z własnymi uprawnieniami konieczne. Zmiana w międzyczasie może odrzucić/prosić o nową. Potwierdzone działania dostępne; usunięcie rozmowy/asystenta ich nie cofa. Usuwa rozmowy, zachowuje historię zatwierdzeń.

Monitoruj sprzęt/Koha, unikaj nowych zdjęć przy spowolnieniu, zwolnij pamięć odpowiednio. Brak gwarantowanego czasu odpowiedzi. Dostawca zdalny otrzymuje dane żądania: sprawdź prywatność/obrazy, nie testuj rzeczywistymi czytelnikami. Etykieta kosztu nie gwarantuje bezpłatności.

**Do potwierdzenia:** RAM/dysk/latencja dla wyboru/sprzętu; minimum Koha nie gwarantuje AI.

## Sprawdzone źródła

- [ai.py](../../../panel/kei_panel/views/ai.py).
- [marcreplace.py](../../../panel/kei_panel/marcreplace.py).
- [installer](../../../installer).
