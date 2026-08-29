# HomeHunter — Produktseite

Statische Einzelseite für Daten- und Schnittstellenpartner. Ein HTML, ein CSS,
ein kurzes Skript für den Sprachumschalter. Kein Build, keine Abhängigkeiten,
keine externen Adressen.

    index.html    Seite, Deutsch und Englisch im selben Dokument
    style.css     Gesamtes Layout, einschließlich Druckfassung (A4)
    favicon.svg   Symbol der Anwendung, aus HomeHunter/assets/homehunter.svg
    img/          vier Bildschirmfotos, 1440 x 900
    tools/        Skript, das die Bildschirmfotos erzeugt
    .nojekyll     GitHub Pages soll nichts verarbeiten

## Ansehen

    python3 -m http.server -d . 8000    # http://localhost:8000

Die Datei lässt sich auch direkt im Browser öffnen; ein Server wird nicht
gebraucht. Gedruckt ergibt die Seite vier Blatt A4.

## Bildschirmfotos neu erzeugen

    cd ~/Projects/HomeHunter
    uv run python ~/Projects/homehunter-site/tools/make_screenshots.py

Das Skript kopiert die Datenbank in ein Wegwerf-Verzeichnis, ersetzt dort das
Bewerberprofil durch ein neutrales Beispielprofil, bewertet einmal neu und
nimmt die vier Ansichten offscreen auf. Es öffnet kein Fenster, es sendet
nichts, und die Daten der laufenden Anwendung bleiben unberührt.

Wichtig: das Anschreiben auf `04-anschreiben.png` entsteht aus dem
Beispielprofil, nicht aus dem echten. Das echte Profil enthält Telefonnummer,
Nettoeinkommen und den Kostenträger der Miete — nichts davon gehört auf eine
öffentliche Seite. Wer die Bilder von Hand austauscht, muss darauf selbst
achten.

## Noch zu ergänzen

**1. Anschrift für das Impressum.** In `index.html` steht zweimal der
Platzhalter `[STRASSE, PLZ BERLIN]` — je einmal in der deutschen und in der
englischen Fußzeile. § 5 TMG verlangt eine ladungsfähige Anschrift; ohne sie
sollte die Seite nicht öffentlich gehen.

**2. Absolute Adressen für die Vorschau.** Sobald die Domäne feststeht, im
`<head>` `og:image` auf eine absolute Adresse setzen und `og:url` ergänzen.
Relative Pfade werten nicht alle Dienste aus, die eine Linkvorschau bauen.

## Veröffentlichen

GitHub Pages, Zweig `master`, Wurzelverzeichnis. Eine eigene Domäne ist
vorzuziehen: eine Adresse auf `github.io` liest sich in einem Geschäftsbrief
schwach. Sobald es eine Domäne gibt, dort auch eine Postadresse einrichten und
diese statt der Gmail-Adresse eintragen — drei Stellen je Sprachfassung: Kopf,
Abschnitt „Status und Kontakt“, Impressum.
