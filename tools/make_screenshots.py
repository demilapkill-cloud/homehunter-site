"""Die vier Bildschirmfotos der Produktseite, offscreen aufgenommen.

Aufruf (die Abhängigkeiten liegen im HomeHunter-Projekt, nicht hier):

    cd ~/Projects/HomeHunter
    uv run python ~/Projects/homehunter-site/tools/make_screenshots.py

Die Datenbank wird vorher in ein Wegwerf-Verzeichnis kopiert; die laufende
Anwendung und die Daten des Nutzers bleiben unberührt. In der Kopie wird die
Überwachung abgeschaltet, `telegram.json` fehlt — die Aufnahme-Instanz kann
also nichts senden — und der angezeigte Name des Suchprofils
wird auf einen deutschen Text gesetzt, damit auf einer deutschen Seite kein
russischer Rest steht. Der Name geht über `compute_preset_hash`
(decision_engine.py) in die Bewertung ein, ein neuer Name macht die
gespeicherten Urteile also veraltet — deshalb wird das gezeigte Angebot nach
dem Start einmal neu bewertet, damit die Hashes wieder zusammenpassen und
kein Warnstreifen erscheint.

Ebenfalls in der Kopie: das Bewerberprofil wird durch ein neutrales
Beispielprofil ersetzt. Das Anschreiben auf dem Bildschirmfoto ist damit ein
Musterbrief und gibt weder Telefonnummer noch Einkommen noch den Kostenträger
der Miete preis.

Es öffnet sich kein Fenster: QT_QPA_PLATFORM=offscreen wird hier erzwungen,
nicht nur vorgeschlagen.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QML_DISABLE_DISK_CACHE"] = "1"

SOURCE_DATA_DIR = Path.home() / "Projects" / "HomeHunter" / "var"
OUT_DIR = Path(__file__).resolve().parent.parent / "img"

WIDTH, HEIGHT = 1440, 900
PRESET_NAME_DE = "Wohnungssuche Berlin"


def clone_data_dir(source: Path) -> Path:
    """Ein konsistenter Abzug der Datenbank, auch während die App schreibt."""
    scratch = Path(tempfile.mkdtemp(prefix="hh-site-shots-"))
    (scratch / "db").mkdir(parents=True)
    db = source / "db" / "homehunter.sqlite3"
    if not db.exists():
        raise SystemExit(f"Keine Datenbank unter {db}")

    src = sqlite3.connect(str(db))
    dst = sqlite3.connect(str(scratch / "db" / "homehunter.sqlite3"))
    with dst:
        src.backup(dst)
    src.close()
    dst.close()

    for name in ("ui-preferences.json", "user-categories.json"):
        if (source / name).exists():
            shutil.copy(source / name, scratch / name)

    conn = sqlite3.connect(str(scratch / "db" / "homehunter.sqlite3"))
    with conn:
        try:
            conn.execute("UPDATE monitor_settings SET enabled = 0")
        except sqlite3.Error:
            pass
        conn.execute("UPDATE search_presets SET name = ?", (PRESET_NAME_DE,))
        # Das Anschreiben wird aus dem Bewerberprofil gebaut. Das echte
        # Profil enthält Telefonnummer, Nettoeinkommen und die Angabe, dass
        # das Jobcenter die Miete trägt — auf einer öffentlichen Seite, die
        # sich an Unternehmen richtet, hat nichts davon etwas zu suchen.
        # Für die Aufnahme steht deshalb ein neutrales Beispielprofil in der
        # Kopie; der erzeugte Brief ist damit ein Musterbrief.
        conn.execute(
            """
            UPDATE applicant_profiles
               SET phone = '+49 30 12345678',
                   employment_status = 'employed',
                   monthly_net_income = 2600.0,
                   benefit_status = NULL,
                   rent_payer = 'self'
            """
        )
    conn.close()
    return scratch


def pick_listing(scratch: Path) -> str:
    """Ein Angebot, das die Seite gut zeigt: bestanden, vollständig, mit Adresse."""
    conn = sqlite3.connect(f"file:{scratch / 'db' / 'homehunter.sqlite3'}?mode=ro", uri=True)
    row = conn.execute(
        """
        SELECT l.id
          FROM listings l
          JOIN listing_decisions d ON d.listing_id = l.id
         WHERE d.classification = 'match'
           AND length(l.title) BETWEEN 12 AND 70
           AND json_extract(l.data, '$.price.rent_total') IS NOT NULL
           AND json_extract(l.data, '$.property.area_m2') IS NOT NULL
           AND json_extract(l.data, '$.property.rooms') IS NOT NULL
           AND json_extract(l.data, '$.address.street') IS NOT NULL
           AND length(json_extract(l.data, '$.description')) > 200
         ORDER BY l.first_seen_at DESC
         LIMIT 1
        """
    ).fetchone()
    if row is None:
        row = conn.execute(
            """
            SELECT listing_id FROM listing_decisions
             WHERE classification = 'match' LIMIT 1
            """
        ).fetchone()
    conn.close()
    if row is None:
        raise SystemExit("Kein passendes Angebot in der Datenbank gefunden.")
    return str(row[0])


def main() -> int:
    scratch = clone_data_dir(SOURCE_DATA_DIR)
    os.environ["HOMEHUNTER_DATA_DIR"] = str(scratch)

    from PySide6.QtCore import QTimer
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtWidgets import QApplication

    from homehunter.application.facade import HomeHunterFacade
    from homehunter.config.settings import Settings
    from homehunter.ui.main_window import MainWindow

    listing_id = pick_listing(scratch)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv[:1])
    facade = HomeHunterFacade(Settings(data_dir=scratch))
    window = MainWindow(facade)
    window.show()
    root = window.root_window
    root.setWidth(WIDTH)
    root.setHeight(HEIGHT)

    bridge = window.bridge
    bridge.setLanguage("de")
    bridge.setDarkMode(False)
    root.setProperty("activePage", "listings")

    def find(name: str):
        """Das *sichtbare* Element mit diesem objectName.

        `findChild` liefert den ersten Treffer im Objektbaum, und das ist
        hier der falsche: der Sichtungsmodus (TriageMode.qml) baut eine
        zweite, verborgene ListingDetailPane, die vor der sichtbaren steht.
        `isVisible()` prüft die tatsächliche Sichtbarkeit einschließlich
        aller Elternelemente und trennt die beiden zuverlässig.
        """
        matches = root.findChildren(QQuickItem, name)
        for item in matches:
            if item.isVisible() and item.height() > 0:
                return item
        return matches[0] if matches else None

    def scroll_to(object_name: str, *, offset: int = -16) -> None:
        """Die Detailspalte auf ein benanntes Element schieben."""
        scroll = find("detailScroll")
        target = find(object_name)
        if scroll is None or target is None:
            print(f"  ! {object_name} nicht gefunden — nicht gescrollt")
            return
        flick = scroll.property("contentItem")
        column = find("detailColumn")
        if flick is None or column is None:
            return
        y = target.mapToItem(column, 0, 0).y() + offset
        max_y = max(0.0, flick.property("contentHeight") - flick.property("height"))
        flick.setProperty("contentY", max(0.0, min(y, max_y)))

    def grab(name: str) -> None:
        path = OUT_DIR / name
        root.grabWindow().save(str(path))
        print(f"  gespeichert: {path.relative_to(OUT_DIR.parent)}")

    steps: list = []

    def step(fn):
        steps.append(fn)
        return fn

    @step
    def _list():
        # Die Vorgabe ist die Registerkarte "Treffer"; die zeigt je nach
        # Datenlage eine einzige Karte. Für ein Bild der Liste "Alle".
        page = find("listingsPage")
        if page is not None:
            page.setProperty("filterVerdict", "ALL")
        bridge.selectListing(listing_id)

    @step
    def _reanalyse():
        # Beispielprofil und deutscher Profilname haben einen anderen Inhalt
        # als das Gespeicherte, also auch andere Hashes — die App hielte jede
        # gespeicherte Bewertung sonst zu Recht für veraltet und blendete
        # einen Warnstreifen ein. Es reicht nicht, nur das ausgewählte Angebot
        # neu zu bewerten: der Sichtungsmodus zeigt andere Karten, und die
        # trügen weiter den alten Profilnamen und einen Hinweis, der das
        # frühere Profil verrät. Deshalb einmal alles.
        bridge.reanalyzeAllListings()

    @step
    def _await_reanalysis():
        # `reanalyzeAllListings` läuft im Hintergrund; ohne Warten wären die
        # Aufnahmen ein Wettlauf. Danach noch 4,5 s, bis der Hinweisstreifen
        # von selbst verschwindet (Toast.qml: 3,8 s).
        waited = {"ms": 0}

        def poll() -> None:
            if not bridge.isReanalyzing or waited["ms"] > 300_000:
                if waited["ms"] > 300_000:
                    print("  ! Neubewertung dauerte zu lange — weiter ohne")
                QTimer.singleShot(4500, tick)
                return
            waited["ms"] += 500
            QTimer.singleShot(500, poll)

        print("  Neubewertung läuft …")
        state["hold"] = True
        QTimer.singleShot(500, poll)

    @step
    def _shoot_list():
        scroll_to("detailScroll", offset=0)
        flick = find("detailScroll").property("contentItem")
        flick.setProperty("contentY", 0.0)
        grab("01-liste.png")

    @step
    def _shoot_reasons():
        scroll_to("decisionSection")
        grab("02-gruende.png")

    @step
    def _open_letter():
        expander = find("letterExpander")
        if expander is None:
            raise SystemExit("letterExpander nicht gefunden — objectName fehlt?")
        expander.setProperty("expanded", True)

    @step
    def _shoot_letter():
        scroll_to("letterExpander")
        grab("04-anschreiben.png")

    @step
    def _open_triage():
        find("letterExpander").setProperty("expanded", False)
        bridge.requestTriage()

    @step
    def _shoot_triage():
        grab("03-sichtung.png")

    state: dict = {"i": 0, "hold": False}

    def tick() -> None:
        i = state["i"]
        if i >= len(steps):
            app.quit()
            return
        state["hold"] = False
        steps[i]()
        state["i"] = i + 1
        # Ein Schritt, der selbst wartet (`hold`), ruft `tick` selbst wieder auf.
        if not state["hold"]:
            QTimer.singleShot(900, tick)

    QTimer.singleShot(2500, tick)
    code = app.exec()
    window.teardown()
    shutil.rmtree(scratch, ignore_errors=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
