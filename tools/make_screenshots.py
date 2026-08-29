"""Die vier Bildschirmfotos der Produktseite, offscreen aufgenommen.

Aufruf (die Abhängigkeiten liegen im HomeHunter-Projekt, nicht hier):

    cd ~/Projects/HomeHunter
    uv run python ~/Projects/homehunter-site/tools/make_screenshots.py

Alles, was auf den Bildern über den *Nutzer* zu sehen ist, steht als
DEMO_PRESET und DEMO_PROFILE weiter unten in dieser Datei: ein erfundenes
Suchprofil und ein erfundener Bewerber, beide eigens für die Webseite. Das
echte Profil wird nicht gelesen und nicht angezeigt. Deshalb darf diese Datei
öffentlich liegen, und deshalb sind die Bilder reproduzierbar: wer sie neu
erzeugt, bekommt dieselbe Ausgangslage.

Echt sind allein die Wohnungsanzeigen — öffentlich ausgeschriebene Angebote,
aus einer Kopie der Datenbank gelesen.

Die Kopie liegt in einem Wegwerf-Verzeichnis: die laufende Anwendung und die
Daten des Nutzers bleiben unberührt, die Überwachung ist darin abgeschaltet
und `telegram.json` fehlt, die Aufnahme-Instanz kann also nichts senden.

Es öffnet sich kein Fenster: QT_QPA_PLATFORM=offscreen wird hier erzwungen,
nicht nur vorgeschlagen.
"""

from __future__ import annotations

import contextlib
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

#: Das Suchprofil, das auf den Bildern zu sehen ist. Frei erfunden, aber an
#: den tatsächlichen Berliner Angeboten ausgerichtet: eine Suche, die fast
#: alles ablehnt, ergibt eine Liste aus lauter roten Karten und erklärt einem
#: Betrachter nichts. Die neuesten Anzeigen im Bestand liegen überwiegend
#: zwischen 1.300 und 2.000 € warm, deshalb diese Grenzen — so stehen Treffer,
#: Prüffälle und Absagen nebeneinander, also genau das, was die Seite über das
#: Regelwerk behauptet.
DEMO_PRESET: dict = {
    "name": "Wohnungssuche Berlin",
    "cities": ["Berlin"],
    "districts": [],
    "min_rooms": 1,
    "max_rooms": 4,
    "min_area_m2": 15,
    "max_area_m2": 120,
    "max_cold_rent": 1700,
    "max_warm_rent": 2000,
    "rent_payer": "self",
}

#: Der Bewerber, aus dem das Anschreiben gebaut wird. Ebenfalls frei erfunden.
#: Der Name bleibt der des Autors, weil er ohnehin im Kopf der Seite steht;
#: alles Übrige — Beschäftigung, Einkommen, Telefonnummer — ist Beispiel und
#: sagt nichts über die tatsächlichen Verhältnisse aus.
DEMO_PROFILE: dict = {
    "first_name": "Damian",
    "last_name": "Lapiha",
    "email": "kontakt@example.com",
    "phone": "+49 30 12345678",
    "household_size": 1,
    "employment_status": "employed",
    "monthly_net_income": 2600.0,
    "wbs_ownership": "no_wbs",
}


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
    with conn, contextlib.suppress(sqlite3.Error):
        conn.execute("UPDATE monitor_settings SET enabled = 0")
        # Die Quelle, die über die eigene Telegram-Sitzung des Nutzers läuft,
        # gehört nicht auf die Produktseite: sie liest einen fremden Kanal,
        # der Anzeigen anderer Anbieter weiterveröffentlicht, und genau diese
        # Anbieter sind die Leser der Seite. Die Seite nennt sie ebenfalls
        # nicht — dort stehen die neunzehn ohne eigene Sitzung abrufbaren
        # Quellen. Die Aufnahme bleibt damit deckungsgleich mit dem Text.
        conn.execute("DELETE FROM source_monitor_states WHERE source LIKE '%telegram%'")
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

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv[:1])
    facade = HomeHunterFacade(Settings(data_dir=scratch))

    # Demo-Werte über die Dienste der Anwendung setzen, nicht per SQL: so
    # laufen sie durch dieselbe Validierung wie eine Eingabe im Programm,
    # und jedes Feld, das hier nicht genannt ist, behält seinen Standard.
    profile = facade.profile_service.save(DEMO_PROFILE)
    active = facade.search_criteria_service.get_active_preset()
    if active is None:
        preset = facade.search_criteria_service.create_preset(DEMO_PRESET)
        facade.search_criteria_service.activate_preset(preset.id)
    else:
        facade.search_criteria_service.update_preset(active.id, DEMO_PRESET)
    print(f"  Demo-Suchprofil und -Bewerber gesetzt ({profile.first_name})")

    listing_id = pick_listing(scratch)
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

    def scroll_to(object_name: str, *, offset: int = -16, scroll_name: str = "detailScroll",
                  column_name: str = "detailColumn") -> None:
        """Eine Bildlaufspalte auf ein benanntes Element schieben."""
        scroll = find(scroll_name)
        target = find(object_name)
        if scroll is None or target is None:
            print(f"  ! {object_name} nicht gefunden — nicht gescrollt")
            return
        flick = scroll.property("contentItem")
        column = find(column_name)
        if flick is None or column is None:
            return
        y = target.mapToItem(column, 0, 0).y() + offset
        max_y = max(0.0, flick.property("contentHeight") - flick.property("height"))
        flick.setProperty("contentY", max(0.0, min(y, max_y)))

    def grab(name: str, *, cut_above: str | None = None,
             cut_left_of: str | None = None, cut_below_top_of: str | None = None) -> None:
        """Aufnehmen und auf einen Ausschnitt beschneiden.

        Die Seite wirbt nicht damit, dass die Anwendung Bewerbungsunterlagen
        zusammenstellt oder ein Anschreiben verfasst. In der Detailspalte
        stehen diese Abschnitte zwischen den Dingen, die hier gezeigt werden
        sollen, also wird der Ausschnitt an ihnen abgeschnitten — geschnitten,
        nicht retuschiert: zu sehen ist, was zu sehen ist, nur weniger davon.

        Alle drei Kanten werden in Fensterkoordinaten bestimmt und erst danach
        gemeinsam angewendet. Nacheinander zu schneiden ginge schief: nach dem
        ersten Schnitt zählt das Bild anders als das Fenster.
        """
        image = root.grabWindow()
        ratio = image.height() / max(1.0, float(root.height()))

        def edge(object_name: str, axis: str) -> float | None:
            marker = find(object_name)
            if marker is None:
                print(f"  ! {object_name} nicht gefunden — Kante entfällt")
                return None
            point = marker.mapToItem(None, 0.0, 0.0)
            return point.x() if axis == "x" else point.y()

        left, top = 0, 0
        right, bottom = image.width(), image.height()

        if cut_left_of is not None:
            x = edge(cut_left_of, "x")
            if x is not None:
                right = min(right, int((x - 8) * ratio))
        if cut_below_top_of is not None:
            y = edge(cut_below_top_of, "y")
            if y is not None:
                top = max(top, int(y * ratio))
        if cut_above is not None:
            y = edge(cut_above, "y")
            if y is not None:
                bottom = min(bottom, int((y - 10) * ratio))

        if right - left > 300 and bottom - top > 200:
            image = image.copy(left, top, right - left, bottom - top)
        else:
            print(f"  ! Ausschnitt für {name} unbrauchbar — ungeschnitten")

        path = OUT_DIR / name
        image.save(str(path))
        size = f"{image.width()}x{image.height()}"
        print(f"  gespeichert: {path.relative_to(OUT_DIR.parent)}  {size}")

    steps: list = []

    def step(fn):
        steps.append(fn)
        return fn

    # Die Seite wirbt nicht damit, dass die Anwendung Bewerbungsunterlagen
    # zusammenstellt oder ein Anschreiben schreibt. Die Aufnahmen dürfen es
    # deshalb auch nicht zeigen: jede Ansicht wird an den Stellen der
    # Detailspalte gegriffen, an denen es um Fund, Urteil und Herkunft geht.

    @step
    def _open_list():
        page = find("listingsPage")
        if page is not None:
            page.setProperty("filterVerdict", "ALL")
        # Die Vorgabe "Neueste zuerst" stellt die frisch eingegangenen
        # möblierten Angebote nach vorn, und die sprengen jedes Budget — die
        # Liste bestünde aus lauter Absagen. "Treffer zuerst" zeigt, wonach
        # ein Suchender die Liste tatsächlich durchgeht.
        #
        # Das Auswahlfeld wird mitgesetzt: `setListingsSortMode` allein ändert
        # nur das Modell, nicht die Beschriftung, und die Aufnahme zeigte sonst
        # eine Reihenfolge, die nicht zu ihrem eigenen Auswahlfeld passt.
        combo = find("sortCombo")
        if combo is not None:
            combo.setProperty("currentIndex", 1)
        bridge.setListingsSortMode("smart")
        bridge.selectListing(listing_id)

    @step
    def _reanalyse():
        # Demo-Suchprofil und -Bewerber haben andere Hashes als das
        # Gespeicherte; ohne Neubewertung stünde auf jeder Karte ein
        # Warnstreifen "Bewertung veraltet". Der Sichtungsmodus zeigt andere
        # Karten als die ausgewählte, deshalb einmal alles.
        bridge.reanalyzeAllListings()

    @step
    def _await_reanalysis():
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
        # Nur die Listenspalte, ohne die Detailspalte daneben und ohne die
        # Kopfzeile darüber: die Aufnahme soll die Liste zeigen, nicht eine
        # angeschnittene Werkzeugleiste.
        grab("01-liste.png", cut_left_of="detailPane", cut_below_top_of="detailPane")

    @step
    def _shoot_verdict():
        # Ein Band aus Liste und Urteil. Direkt unter dem Urteil steht in der
        # Anwendung die Vollständigkeit der Bewerbungsunterlagen — davon ist
        # auf dieser Seite nicht die Rede, also endet das Bild davor.
        scroll_to("decisionSection")
        grab("02-urteil.png", cut_above="readinessSection")

    @step
    def _shoot_origin():
        # Und ein zweites Band: Datenqualität, Originaltext und die Quelle mit
        # dem Link auf das ursprüngliche Exposé — der Teil, der einen
        # Datenpartner angeht. Es endet vor "Meine Bewerbung".
        scroll_to("sourcesSection", offset=-24)
        grab("03-herkunft.png",
             cut_below_top_of="dataQualitySection", cut_above="myApplicationSection")

    @step
    def _open_overview():
        # Die Übersicht trägt die Quellenliste mit ihrem jeweiligen Zustand —
        # für einen Datenpartner die aussagekräftigste Ansicht der Anwendung,
        # weil dort auch die gesperrten Quellen mit ihrem Grund stehen.
        root.setProperty("activePage", "home")

    @step
    def _expand_sources():
        panel = find("monitorPanel")
        if panel is not None:
            panel.setProperty("sourcesExpanded", True)

    @step
    def _scroll_past_first_source():
        # Die erste Zeile der Quellenliste ist die, die über die eigene
        # Telegram-Sitzung des Nutzers läuft. Sie kommt aus dem Verzeichnis
        # der Anwendung, nicht aus der Datenbank, lässt sich also nicht
        # herauslöschen — die Liste wird stattdessen so weit geschoben, dass
        # sie über dem Bildrand steht. Der Kopf der Karte geht dabei mit;
        # gezeigt werden soll ohnehin die Liste selbst.
        scroll = find("dashboardScroll")
        panel = find("monitorPanel")
        if scroll is None or panel is None:
            print("  ! Übersicht nicht gefunden — ungescrollt")
            return
        flick = scroll.property("contentItem")
        top = panel.mapToItem(None, 0.0, 0.0).y()
        flick.setProperty("contentY", float(flick.property("contentY")) + top + 305.0)

    @step
    def _shoot_sources_panel():
        grab("04-quellenliste.png", cut_above="applicationsSection")

    @step
    def _open_criteria():
        root.setProperty("activePage", "search")

    @step
    def _shoot_criteria():
        grab("05-kriterien.png")

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
