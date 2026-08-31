from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import (QApplication, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QProgressBar, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)
except ImportError as exc:
    raise RuntimeError("Install the desktop extra: pip install -e '.[desktop]'") from exc

from .adapters import GenericWebAdapter
from .db import Database
from .job import JobController
from .models import JobConfig


class MainWindow(QMainWindow):
    COLUMNS = ["Job", "Source", "Stage", "Progress", "Completed", "Failed", "Current resource", "Status"]
    def __init__(self):
        super().__init__(); self.setWindowTitle("Universal Resource Collector"); self.resize(1100,650); self.controllers={}; self.rows={}; self.last_status={}
        root=QWidget(); outer=QVBoxLayout(root); form=QGridLayout(); self.url=QLineEdit(); self.output=QLineEdit(str(Path.home()/"ResourceCollections")); browse=QPushButton("Browse"); form.addWidget(QLabel("Source URL"),0,0); form.addWidget(self.url,0,1,1,3); form.addWidget(QLabel("Output"),1,0); form.addWidget(self.output,1,1,1,2); form.addWidget(browse,1,3); outer.addLayout(form)
        actions=QHBoxLayout(); self.start_button=QPushButton("Start new job"); self.pause_button=QPushButton("Pause selected"); self.resume_button=QPushButton("Resume selected"); self.cancel_button=QPushButton("Cancel selected"); actions.addWidget(self.start_button); actions.addWidget(self.pause_button); actions.addWidget(self.resume_button); actions.addWidget(self.cancel_button); outer.addLayout(actions)
        self.table=QTableWidget(0,len(self.COLUMNS)); self.table.setHorizontalHeaderLabels(self.COLUMNS); self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setAlternatingRowColors(True); self.table.setSortingEnabled(False); self.table.horizontalHeader().setStretchLastSection(True); outer.addWidget(self.table)
        self.overall=QProgressBar(); self.overall.setFormat("Selected job: %p% "); outer.addWidget(self.overall); self.log=QTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(130); outer.addWidget(self.log); self.setCentralWidget(root)
        browse.clicked.connect(self.choose_output); self.start_button.clicked.connect(self.start_job); self.pause_button.clicked.connect(lambda: self.control_selected("pause")); self.resume_button.clicked.connect(lambda: self.control_selected("resume")); self.cancel_button.clicked.connect(lambda: self.control_selected("cancel")); self.table.itemSelectionChanged.connect(self.refresh_selected_progress)
        self.timer=QTimer(self); self.timer.timeout.connect(self.refresh_jobs); self.timer.start(500)

    def choose_output(self):
        path=QFileDialog.getExistingDirectory(self,"Select output folder");
        if path: self.output.setText(path)

    def start_job(self):
        source=self.url.text().strip(); output=self.output.text().strip(); domain=urlparse(source).hostname if source else None
        if not source or not output or not domain: QMessageBox.warning(self,"Missing input","Enter a valid source URL and output folder."); return
        db=Database(Path(output)/"collection.db"); controller=JobController(db,JobConfig(source,output,[domain]),GenericWebAdapter([domain])); self.controllers[controller.job_id]=controller; self.add_job_row(controller.job_id,source); controller.start(); self.log.append(f"Job {controller.job_id} started: {source}"); self.url.selectAll()

    def add_job_row(self,job_id,source):
        row=self.table.rowCount(); self.table.insertRow(row); self.rows[job_id]=row
        for col,value in enumerate((str(job_id),source,"Queued","0 / discovering","0","0","-","created")): self.table.setItem(row,col,QTableWidgetItem(value))
        self.table.setCellWidget(row,3,QProgressBar()); self.table.cellWidget(row,3).setFormat("%p%")
        self.table.resizeColumnsToContents()

    def selected_job_id(self):
        rows=self.table.selectionModel().selectedRows();
        if not rows: return None
        value=self.table.item(rows[0].row(),0); return int(value.text()) if value else None

    def control_selected(self,action):
        job_id=self.selected_job_id(); controller=self.controllers.get(job_id)
        if controller: getattr(controller,action)(); self.log.append(f"Job {job_id}: {action}")

    def snapshot(self,controller):
        db=controller.db; job=db.conn.execute("SELECT status,total_resources FROM jobs WHERE id=?",(controller.job_id,)).fetchone(); total=int(job["total_resources"] or 0); counts=db.conn.execute("SELECT COUNT(*) AS total, SUM(CASE WHEN status IN ('downloaded','converted','validating','passed','warning','auditing','human_review') THEN 1 ELSE 0 END) AS complete, SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed FROM resources WHERE job_id=?",(controller.job_id,)).fetchone(); current=db.conn.execute("SELECT url,status FROM resources WHERE job_id=? AND status IN ('downloading','downloaded','converting','validating') ORDER BY id DESC LIMIT 1",(controller.job_id,)).fetchone(); pages=db.conn.execute("SELECT COUNT(*) FROM source_pages WHERE job_id=?",(controller.job_id,)).fetchone()[0]; return {"status":job["status"],"total":total or int(counts["total"] or 0),"complete":int(counts["complete"] or 0),"failed":int(counts["failed"] or 0),"current":current["url"] if current else "-","stage":job["status"],"pages":pages}

    def refresh_jobs(self):
        for job_id,controller in list(self.controllers.items()):
            try: self.update_row(job_id,self.snapshot(controller))
            except Exception as exc: self.log.append(f"Job {job_id} monitor error: {exc}")
        self.refresh_selected_progress()

    def update_row(self,job_id,s):
        row=self.rows[job_id]; total=s["total"]; complete=s["complete"]; percent=int(complete*100/total) if total else 0; self.table.item(row,2).setText(f"{s['stage']} · {s['pages']} pages"); self.table.item(row,4).setText(str(complete)); self.table.item(row,5).setText(str(s["failed"])); self.table.item(row,6).setText(s["current"]); self.table.item(row,7).setText(s["status"]); bar=self.table.cellWidget(row,3); bar.setValue(percent); bar.setFormat(f"{complete}/{total} (%p%)")
        status_key=(s["status"],complete,s["failed"])
        if self.last_status.get(job_id)!=status_key and s["status"] in {"completed","failed","cancelled","paused"}: self.log.append(f"Job {job_id}: {s['status']} — {complete}/{total} complete, {s['failed']} failed"); self.last_status[job_id]=status_key

    def refresh_selected_progress(self):
        job_id=self.selected_job_id(); controller=self.controllers.get(job_id)
        if not controller: self.overall.setValue(0); return
        s=self.snapshot(controller); self.overall.setValue(int(s["complete"]*100/s["total"]) if s["total"] else 0); self.overall.setFormat(f"Job {job_id}: {s['complete']}/{s['total']} resources · {s['status']}")


def main():
    app=QApplication(sys.argv); window=MainWindow(); window.show(); return app.exec()
