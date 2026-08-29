# HomeHunter — Produktseite

Statische Einzelseite für Daten- und Schnittstellenpartner. Ein HTML, ein CSS,
ein kurzes Skript für den Sprachumschalter. Kein Build, keine Abhängigkeiten,
keine externen Adressen.

    index.html    Seite, Deutsch und Englisch im selben Dokument
    style.css     Gesamtes Layout, einschließlich Druckfassung (A4)
    favicon.svg   Symbol der Anwendung, aus HomeHunter/assets/homehunter.svg
    img/          fünf Bildschirmfotos aus der Anwendung
    tools/        Skript, das die Bildschirmfotos erzeugt
    .nojekyll     GitHub Pages soll nichts verarbeiten
    CNAME         www.homehunter.store

Die Seite steht auf `noindex, nofollow`: sie wird gezielt weitergegeben und
soll nicht über eine Suchmaschine zu finden sein. Ein `robots.txt` liegt
bewusst nicht daneben — eine dort gesperrte Datei liest kein Crawler, und
dann bliebe auch die `noindex`-Zeile ungelesen.

## Ansehen

    python3 -m http.server -d . 8000    # http://localhost:8000

Die Datei lässt sich auch direkt im Browser öffnen; ein Server wird nicht
gebraucht. Gedruckt ergibt die Seite fünf Blatt A4; das letzte trägt
Impressum und Datenschutzerklärung.

## Bildschirmfotos neu erzeugen

    cd ~/Projects/HomeHunter
    uv run python ~/Projects/homehunter-site/tools/make_screenshots.py

Das Skript kopiert die Datenbank in ein Wegwerf-Verzeichnis, ersetzt dort das
Bewerberprofil durch ein neutrales Beispielprofil, bewertet einmal neu und
nimmt die fünf Ansichten offscreen auf. Es öffnet kein Fenster, es sendet
nichts, und die Daten der laufenden Anwendung bleiben unberührt.

Wichtig: alles, was auf den Bildern über den *Nutzer* zu sehen ist, stammt aus
dem Beispielprofil im Skript, nicht aus dem echten. Das echte Profil enthält
Telefonnummer, Nettoeinkommen und den Kostenträger der Miete — nichts davon
gehört auf eine Seite, die aus dem Haus geht. Wer die Bilder von Hand
austauscht, muss darauf selbst achten.

Echt sind allein die Wohnungsanzeigen: öffentlich ausgeschriebene Angebote aus
einer Kopie der Datenbank. Auf `01-liste.png` stehen deshalb Überschriften
fremder Inserate.

## Noch zu ergänzen

**Sichtbarkeit des Repositorys.** Dieses Repository ist öffentlich, und das
bleibt es. Die `noindex`-Zeile hält die Seite aus den Suchmaschinen heraus,
nicht aber aus GitHub: wer das Repository findet, findet die Adresse. Alles,
was hier steht — auch diese Datei —, ist damit öffentlich; interne Notizen
gehören entsprechend nicht hinein.

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
