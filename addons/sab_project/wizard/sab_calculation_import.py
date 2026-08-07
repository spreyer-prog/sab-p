import base64
import io

from odoo import fields, models
from odoo.exceptions import UserError


class SabCalculationImport(models.TransientModel):
    _name = "sab.calculation.import"
    _description = "SAB-P Kalkulationsdatenbank importieren"

    file_data = fields.Binary(
        string="Excel-Datei",
        required=True,
        attachment=False,
    )

    filename = fields.Char(
        string="Dateiname",
    )

    state = fields.Selection(
        selection=[
            ("upload", "Datei auswählen"),
            ("checked", "Datei geprüft"),
        ],
        string="Status",
        default="upload",
        readonly=True,
    )

    workbook_info = fields.Text(
        string="Prüfergebnis",
        readonly=True,
    )

    detected_sheet_count = fields.Integer(
        string="Anzahl Tabellenblätter",
        readonly=True,
    )

    detected_row_count = fields.Integer(
        string="Erkannte Zeilen",
        readonly=True,
    )

    def _get_file_extension(self):
        self.ensure_one()

        filename = (self.filename or "").strip().lower()

        if filename.endswith(".xls"):
            return "xls"

        if filename.endswith(".xlsx"):
            return "xlsx"

        return False

    def _read_xls_workbook(self, file_content):
        try:
            import xlrd
        except ImportError as exc:
            raise UserError(
                "Die Python-Bibliothek 'xlrd' ist auf dem Odoo.sh-System "
                "nicht installiert. Bitte requirements.txt prüfen."
            ) from exc

        try:
            workbook = xlrd.open_workbook(
                file_contents=file_content,
                on_demand=True,
            )
        except Exception as exc:
            raise UserError(
                "Die XLS-Datei konnte nicht gelesen werden.\n\n"
                f"Technische Meldung:\n{exc}"
            ) from exc

        sheets = []
        total_rows = 0

        for sheet_name in workbook.sheet_names():
            sheet = workbook.sheet_by_name(sheet_name)

            sheets.append(
                {
                    "name": sheet_name,
                    "rows": sheet.nrows,
                    "columns": sheet.ncols,
                }
            )

            total_rows += sheet.nrows

        workbook.release_resources()

        return sheets, total_rows

    def _read_xlsx_workbook(self, file_content):
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise UserError(
                "Die Python-Bibliothek 'openpyxl' ist auf dem Odoo.sh-System "
                "nicht installiert."
            ) from exc

        try:
            workbook = load_workbook(
                filename=io.BytesIO(file_content),
                read_only=True,
                data_only=True,
            )
        except Exception as exc:
            raise UserError(
                "Die XLSX-Datei konnte nicht gelesen werden.\n\n"
                f"Technische Meldung:\n{exc}"
            ) from exc

        sheets = []
        total_rows = 0

        for worksheet in workbook.worksheets:
            row_count = worksheet.max_row or 0
            column_count = worksheet.max_column or 0

            sheets.append(
                {
                    "name": worksheet.title,
                    "rows": row_count,
                    "columns": column_count,
                }
            )

            total_rows += row_count

        workbook.close()

        return sheets, total_rows

    def action_check_file(self):
        self.ensure_one()

        if not self.file_data:
            raise UserError(
                "Bitte zuerst die SAB-P Kalkulationsdatenbank auswählen."
            )

        extension = self._get_file_extension()

        if not extension:
            raise UserError(
                "Es werden nur Excel-Dateien im Format .xls oder .xlsx unterstützt."
            )

        try:
            file_content = base64.b64decode(self.file_data)
        except Exception as exc:
            raise UserError(
                "Die hochgeladene Datei konnte nicht verarbeitet werden."
            ) from exc

        if not file_content:
            raise UserError(
                "Die hochgeladene Datei ist leer."
            )

        if extension == "xls":
            sheets, total_rows = self._read_xls_workbook(file_content)
        else:
            sheets, total_rows = self._read_xlsx_workbook(file_content)

        if not sheets:
            raise UserError(
                "In der Excel-Datei wurden keine Tabellenblätter gefunden."
            )

        info_lines = [
            "SAB-P Kalkulationsdatenbank erfolgreich gelesen.",
            "",
            f"Datei: {self.filename or '-'}",
            f"Format: .{extension}",
            f"Tabellenblätter: {len(sheets)}",
            f"Zeilen gesamt: {total_rows}",
            "",
            "Gefundene Tabellenblätter:",
        ]

        for sheet in sheets:
            info_lines.append(
                f"- {sheet['name']}: "
                f"{sheet['rows']} Zeilen / "
                f"{sheet['columns']} Spalten"
            )

        info_lines.extend(
            [
                "",
                "Es wurden noch keine Daten in die "
                "SAB-P Kalkulationsdatenbank importiert.",
                "",
                "Die eigentliche Spaltenzuordnung erfolgt im nächsten Schritt "
                "nach dem festgelegten SAB-P Konzept.",
                "",
                "Feststehend:",
                "- Spalte R = Kalkulations-/Angebotstext",
                "- 20 Suchbegriffe je Kalkulationsartikel bleiben verfügbar",
                "- DATANORM wird hier nicht importiert",
                "- DATANORM-Artikel werden später den Kalkulationsartikeln zugeordnet",
            ]
        )

        self.write(
            {
                "state": "checked",
                "workbook_info": "\n".join(info_lines),
                "detected_sheet_count": len(sheets),
                "detected_row_count": total_rows,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "name": "Kalkulationsdatenbank importieren",
            "res_model": "sab.calculation.import",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_reset(self):
        self.ensure_one()

        self.write(
            {
                "state": "upload",
                "workbook_info": False,
                "detected_sheet_count": 0,
                "detected_row_count": 0,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "name": "Kalkulationsdatenbank importieren",
            "res_model": "sab.calculation.import",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }