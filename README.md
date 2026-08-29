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

**Anschrift für das Impressum.** In `index.html` steht zweimal der Platzhalter
`[STRASSE, PLZ BERLIN]` — je einmal in der deutschen und in der englischen
Fußzeile. § 5 TMG verlangt eine ladungsfähige Anschrift; ohne sie sollte die
Seite nicht öffentlich gehen.

**Postadresse auf der eigenen Domäne.** Solange es kein Postfach auf
`homehunter.store` gibt, steht die Gmail-Adresse auf der Seite: eine Adresse,
die niemand liest, ist schlechter als eine, die schwächer aussieht. Sobald das
Postfach läuft, sind es drei Stellen je Sprachfassung — Kopf, Abschnitt
„Status und Kontakt“, Impressum.

## Veröffentlichen

Die Domäne ist `homehunter.store` (Squarespace, registriert am 29.08.2026).
`CNAME` in diesem Verzeichnis enthält sie bereits, GitHub Pages liest die Datei
beim Ausrollen.

### DNS bei Squarespace

Die vorhandenen A-Einträge zeigen auf die Parkseite von Squarespace
(198.49.23.144/145, 198.185.159.144/145) und müssen weg. Stattdessen:

| Typ | Host | Wert |
|---|---|---|
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |
| AAAA | @ | 2606:50c0:8000::153 |
| AAAA | @ | 2606:50c0:8001::153 |
| AAAA | @ | 2606:50c0:8002::153 |
| AAAA | @ | 2606:50c0:8003::153 |
| CNAME | www | `<konto>.github.io.` |

Danach im Repository unter Settings → Pages die Domäne eintragen und
„Enforce HTTPS“ setzen, sobald das Zertifikat ausgestellt ist (dauert nach der
DNS-Umstellung meist einige Minuten bis zu einer Stunde).

Prüfen lässt sich das so:

    dig +short A homehunter.store        # die vier 185.199.x.153
    curl -sI https://homehunter.store/ | head -1

### ICANN-Bestätigung

Squarespace zeigt „Action Required“. Bei einer Domäne, die gerade erst
registriert wurde, ist das fast immer die ICANN-Bestätigung der
Registranten-E-Mail: Es kommt eine Mail mit einem Bestätigungslink, und wird
er nicht innerhalb von 15 Tagen angeklickt, sperrt die Registrierungsstelle
die Domäne. Das kann nur der Inhaber selbst erledigen.
