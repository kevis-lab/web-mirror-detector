import sys, asyncio, re, threading, io, os
import pandas as pd
from urllib.parse import urlparse
from network import get_host_and_ips
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QProgressBar, QHeaderView, QFileDialog, QMessageBox, QCheckBox, QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QColor, QPixmap, QImage
from PIL import Image
import imagehash
from pyppeteer import launch
from detector import generate_candidate_urls, check_candidate_urls


class SignalEmitter(QObject):
    progress_signal = pyqtSignal(int, int)
    result_signal = pyqtSignal(list)
    finished_signal = pyqtSignal()
    status_msg = pyqtSignal(str)

async def run_logic(ref_url_raw, start_num, end_num, extra_tlds, prefix_active, suffix_active, emitter, stop_event):
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe", 
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    ]
    exe_path = next((p for p in chrome_paths if os.path.exists(p)), None)
    
    ref_url = ref_url_raw if ref_url_raw.startswith("http") else "https://" + ref_url_raw
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    browser = await launch(executablePath=exe_path, headless=True, handleSIGINT=False, handleSIGTERM=False, handleSIGHUP=False, 
                            args=['--no-sandbox', f'--user-agent={USER_AGENT}', '--ignore-certificate-errors'])
    
    try:
        page = await browser.newPage()
        await page.setUserAgent(USER_AGENT)
        await page.setViewport({'width': 1280, 'height': 800})
        
        if stop_event.is_set(): return
        emitter.status_msg.emit(f"Načítám referenci: {ref_url}")
        ref_hash = None
        results = {}
        
        try:
            await page.goto(ref_url, {'waitUntil': 'networkidle2', 'timeout': 30000})
            await asyncio.sleep(2)
            ref_img_bytes = await page.screenshot({'type': 'png'})
            ref_hash = imagehash.phash(Image.open(io.BytesIO(ref_img_bytes)))
            hostname, ips = get_host_and_ips(ref_url)

            results["REFERENCE"] = {
                'cíl': ref_url,
                'hostname': hostname,
                'ips': ips,
                'status': 200,
                'sim': 100,
                'img': ref_img_bytes,
                'name': ref_url
            }

            emitter.result_signal.emit([[
                d['name'],
                "REFERENČNÍ" if k == "REFERENCE" else "TESTOVANÁ",
                d['cíl'],
                d.get('hostname', ''),
                d.get('ips', ''),
                d['status'],
                d['sim'],
                d['img']
            ] for k, d in results.items()])
        except: pass

        urls_to_check = generate_candidate_urls(
            ref_url,
            start_num,
            end_num,
            extra_tlds,
            prefix_active,
            suffix_active
        )

        emitter.status_msg.emit(f"Prověřuji {len(urls_to_check)} variant...")

        results.update(
            await check_candidate_urls(
                urls_to_check,
                USER_AGENT,
                stop_event
            )
        )

        to_photo = [u for u in results if u != "REFERENCE"]
        for i, u in enumerate(to_photo):
            if stop_event.is_set(): break
            emitter.status_msg.emit(f"Srovnávám {i+1}/{len(to_photo)}: {u}")
            try:
                await page.goto(results[u]['cíl'], {'waitUntil': 'networkidle2', 'timeout': 20000})
                await asyncio.sleep(1.5)
                test_shot = await page.screenshot({'type': 'png'})
                sim_val = 0
                if ref_hash:
                    test_hash = imagehash.phash(Image.open(io.BytesIO(test_shot)))
                    sim_val = int((1 - ((ref_hash - test_hash) / 64.0)) * 100)
                results[u]['sim'] = max(0, sim_val); results[u]['img'] = test_shot
            except: continue
            emitter.result_signal.emit([[
                d['name'],
                "REFERENČNÍ" if k == "REFERENCE" else "TESTOVANÁ",
                d['cíl'],
                d.get('hostname', ''),
                d.get('ips', ''),
                d['status'],
                d['sim'],
                d['img']
            ] for k, d in results.items()])
            emitter.progress_signal.emit(i + 1, len(to_photo))
    finally:
        await browser.close()
        emitter.finished_signal.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Web Mirror Detector Pro")
        self.setGeometry(100, 100, 1600, 900)
        self.emitter = SignalEmitter()
        self.stop_event = threading.Event()
        
        main_layout = QVBoxLayout(); main_layout.setContentsMargins(25, 25, 25, 25)

        btn_style = "QPushButton { border-radius: 6px; font-weight: bold; font-size: 13px; padding: 10px 18px; color: white; }"
        input_style = "QLineEdit { border: 1px solid #ccc; border-radius: 4px; padding: 5px; font-size: 13px; }"

        top_row = QHBoxLayout(); top_row.setSpacing(30)
        
        # URL
        url_box = QVBoxLayout(); url_box.setSpacing(2)
        url_box.addWidget(QLabel("<b>Referenční URL:</b>"))
        self.url_edit = QLineEdit(); self.url_edit.setStyleSheet(input_style); self.url_edit.setFixedWidth(220); self.url_edit.setMinimumHeight(35)
        self.url_edit.textChanged.connect(self.auto_detect_logic)
        url_box.addWidget(self.url_edit)
        url_box.addWidget(self.create_help("(vzor pro srovnání)"))
        top_row.addLayout(url_box)

        # Koncovky
        tld_box = QVBoxLayout(); tld_box.setSpacing(2)
        tld_box.addWidget(QLabel("<b>Koncovky:</b>"))
        tld_grid = QHBoxLayout(); tld_grid.setSpacing(8)
        self.tlds = {}
        for tld in ["cz", "com", "bet", "win", "top", "vip", "online", "site", "games", "fun"]:
            cb = QCheckBox(f".{tld}"); self.tlds[tld] = cb; tld_grid.addWidget(cb)
        tld_box.addLayout(tld_grid)
        tld_box.addWidget(self.create_help("(více koncovek najednou)"))
        top_row.addLayout(tld_box)

        # Rozsah (Upraveno na 1000)
        range_box = QVBoxLayout(); range_box.setSpacing(2)
        range_box.addWidget(QLabel("<b>Rozsah čísel:</b>"))
        range_in = QHBoxLayout(); range_in.setSpacing(5)
        self.start_edit = QLineEdit("1"); self.start_edit.setFixedWidth(45); self.start_edit.setAlignment(Qt.AlignCenter); self.start_edit.setStyleSheet(input_style)
        self.end_edit = QLineEdit("1000"); self.end_edit.setFixedWidth(55); self.end_edit.setAlignment(Qt.AlignCenter); self.end_edit.setStyleSheet(input_style)
        range_in.addWidget(self.start_edit); range_in.addWidget(QLabel("-")); range_in.addWidget(self.end_edit)
        range_box.addLayout(range_in)
        range_box.addWidget(self.create_help("(vč. domény bez čísla)"))
        top_row.addLayout(range_box)

        # Pozice
        pos_box = QVBoxLayout(); pos_box.setSpacing(2)
        pos_box.addWidget(QLabel("<b>Pozice čísla:</b>"))
        pos_layout = QHBoxLayout()
        self.check_prefix = QCheckBox("Před"); self.check_suffix = QCheckBox("Za")
        pos_layout.addWidget(self.check_prefix); pos_layout.addWidget(self.check_suffix)
        pos_box.addLayout(pos_layout)
        pos_box.addWidget(self.create_help("(kde hledat číslovky)"))
        top_row.addLayout(pos_box)

        top_row.addStretch(1)

        # Tlačítka
        self.btn_run = QPushButton("START DETEKCE"); self.btn_run.setStyleSheet(btn_style + "QPushButton { background-color: #2e7d32; border: 1px solid #1b5e20; } QPushButton:hover { background-color: #388e3c; }")
        self.btn_run.clicked.connect(self.start)
        self.btn_stop = QPushButton("STOP"); self.btn_stop.setEnabled(False); self.btn_stop.setStyleSheet(btn_style + "QPushButton { background-color: #d32f2f; border: 1px solid #b71c1c; } QPushButton:hover { background-color: #e53935; }")
        self.btn_stop.clicked.connect(lambda: self.stop_event.set())
        self.btn_export = QPushButton("EXPORT EXCEL"); self.btn_export.setStyleSheet(btn_style + "QPushButton { background-color: #1565c0; border: 1px solid #0d47a1; } QPushButton:hover { background-color: #1976d2; }")
        self.btn_export.clicked.connect(self.export_excel)
        
        top_row.addWidget(self.btn_run); top_row.addWidget(self.btn_stop); top_row.addWidget(self.btn_export)
        
        main_layout.addLayout(top_row)
        main_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Fixed))

        self.status_lbl = QLabel("Připraven"); self.status_lbl.setStyleSheet("font-weight: bold; color: #444;")
        main_layout.addWidget(self.status_lbl)
        self.pbar = QProgressBar(); self.pbar.setMinimumHeight(20); self.pbar.setStyleSheet("QProgressBar { border: 1px solid #bbb; border-radius: 10px; text-align: center; } QProgressBar::chunk { background-color: #4caf50; border-radius: 10px; }")
        main_layout.addWidget(self.pbar)
        
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Doména",
            "Typ",
            "Cílová URL",
            "Hostname",
            "IP adresy",
            "Kód",
            "Shoda %",
            "Náhled"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(100)
        self.table.setStyleSheet("QTableWidget { gridline-color: #eee; border: 1px solid #ddd; } QHeaderView::section { background-color: #f8f8f8; font-weight: bold; border: 1px solid #ddd; }")
        main_layout.addWidget(self.table)

        self.setCentralWidget(QWidget()); self.centralWidget().setLayout(main_layout)
        self.emitter.result_signal.connect(self.update_table)
        self.emitter.progress_signal.connect(lambda c, t: self.pbar.setValue(int(c/t*100) if t > 0 else 0))
        self.emitter.status_msg.connect(self.status_lbl.setText)
        self.emitter.finished_signal.connect(self.on_finish)

    def create_help(self, text):
        l = QLabel(text); l.setStyleSheet("color: #888; font-size: 10px; margin-top: -2px;"); return l

    def auto_detect_logic(self):
        text = self.url_edit.text().lower().replace("http://", "").replace("https://", "").replace("www.", "")
        if not text: return
        if "." in text:
            tld = text.split('.')[-1]
            if tld in self.tlds:
                for cb in self.tlds.values(): cb.setChecked(False)
                self.tlds[tld].setChecked(True)
        domain_part = text.split('.')[0]
        has_prefix = bool(re.match(r'^\d+', domain_part))
        has_suffix = bool(re.search(r'\d+$', domain_part))
        self.check_prefix.setChecked(has_prefix)
        self.check_suffix.setChecked(has_suffix or (not has_prefix and not has_suffix))

    def start(self):
        try:
            url, s, e = self.url_edit.text() or "example.com", int(self.start_edit.text()), int(self.end_edit.text())
            extra = [tld for tld, cb in self.tlds.items() if cb.isChecked()]
            pre, suf = self.check_prefix.isChecked(), self.check_suffix.isChecked()
            if not extra: return QMessageBox.warning(self, "Chyba", "Vyberte koncovku!")
            self.btn_run.setEnabled(False); self.btn_stop.setEnabled(True); self.stop_event.clear(); self.table.setRowCount(0)
            threading.Thread(target=lambda: asyncio.run(run_logic(url, s, e, extra, pre, suf, self.emitter, self.stop_event)), daemon=True).start()
        except: QMessageBox.critical(self, "Chyba", "Chybný rozsah!")

    def on_finish(self):
        self.btn_run.setEnabled(True); self.btn_stop.setEnabled(False); self.status_lbl.setText("Hotovo")

    def update_table(self, data):
        self.current_data = data

        data.sort(key=lambda x: (
            x[1] != "REFERENČNÍ",
            x[5] != 200,
            -x[6]
        ))

        self.table.setRowCount(len(data))

        for i, row in enumerate(data):

            for j in range(7):
                item = QTableWidgetItem(f"{row[j]} %" if j == 6 else str(row[j]))

                if "REFERENČNÍ" in row[1]:
                    item.setBackground(QColor("#fff9c4"))
                elif row[5] == 200:
                    item.setBackground(QColor("#f1f8e9"))

                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, j, item)

            if row[7]:
                pix = QPixmap.fromImage(
                    QImage.fromData(row[7])
                ).scaled(180, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                lbl = QLabel()
                lbl.setPixmap(pix)
                lbl.setAlignment(Qt.AlignCenter)
                self.table.setCellWidget(i, 7, lbl)

    def export_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Uložit",
            "vysledky.xlsx",
            "Excel (*.xlsx)"
        )

        if path:
            pd.DataFrame([
                {
                    "Doména": r[0],
                    "Typ": r[1],
                    "URL": r[2],
                    "Hostname": r[3],
                    "IP adresy": r[4],
                    "Kód": r[5],
                    "Shoda %": r[6]
                }
                for r in self.current_data
            ]).to_excel(path, index=False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())   