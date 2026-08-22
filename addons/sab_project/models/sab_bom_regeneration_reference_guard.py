from odoo import fields, models, _
from odoo.exceptions import ValidationError


class SaleOrderBomRegenerationReferenceGuard(models.Model):
    _inherit = "sale.order"

    def _sab_bom_has_downstream_references(self, bom):
        """Return whether a cabinet BOM is already used by a downstream process.

        Procurement packages deliberately keep links to both the source cabinet
        BOM and the exact source BOM line. Once either link exists, regenerating
        by deleting/recreating those lines would destroy the audit trail and is
        blocked by PostgreSQL's restrict foreign key as well.
        """
        self.ensure_one()
        if not bom or getattr(bom, "bom_scope", "total") != "cabinet":
            return False

        if bom.line_ids and self.env["sab.project.bom.line"].search_count(
            [("source_cabinet_line_id", "in", bom.line_ids.ids)]
        ):
            return True

        return bool(
            self.env["sab.project.bom"].search_count(
                [
                    ("bom_scope", "=", "procurement"),
                    ("source_cabinet_bom_ids", "in", bom.id),
                ]
            )
        )

    def _sab_prepare_or_update_bom(self, scope, cabinet=False, line_commands=None):
        self.ensure_one()
        Bom = self.env["sab.project.bom"]
        domain = [("order_id", "=", self.id), ("bom_scope", "=", scope)]
        if scope == "cabinet":
            domain.append(("cabinet_line_id", "=", cabinet.id))
        bom = Bom.search(domain, limit=1)
        name = (
            f"STL {self.sab_offer_reference or self.name} / {cabinet.description}"
            if scope == "cabinet"
            else f"STL {self.sab_offer_reference or self.name} / GESAMT"
        )

        # Released BOMs and BOMs already referenced by procurement are historic
        # source documents. Their line IDs must remain stable permanently.
        if bom and (
            bom.state == "released"
            or self._sab_bom_has_downstream_references(bom)
        ):
            return bom

        values = {
            "name": name,
            "project_id": self.sab_project_id.id,
            "order_id": self.id,
            "bom_scope": scope,
            "cabinet_line_id": cabinet.id if cabinet else False,
            "generated_at": fields.Datetime.now(),
            "generated_by_id": self.env.user.id,
            "line_ids": [(5, 0, 0)] + (line_commands or []),
        }
        if bom:
            bom.write(values)
        else:
            bom = Bom.create(values)
        return bom

    def action_generate_sab_bom(self):
        self.ensure_one()
        if self.state not in ("sale", "done"):
            raise ValidationError(
                _("Die SAB-P Stückliste kann erst aus einem bestätigten Auftrag erzeugt werden.")
            )
        if not self.sab_project_id:
            raise ValidationError(_("Dem Auftrag ist kein SAB-P Projekt zugeordnet."))
        if self.sab_calculation_source != "schematic":
            raise ValidationError(
                _(
                    "Aus einem reinen LV-Angebot darf keine Stückliste erzeugt werden. "
                    "Stücklisten werden ausschließlich aus einem bestätigten Schaltplan-Angebot "
                    "mit abgegrenzten Schaltschränken erzeugt."
                )
            )
        if not self.sab_calculation_line_ids:
            raise ValidationError(_("Der Auftrag enthält keine SAB-P Kalkulationspositionen."))

        self._sab_validate_schematic_lv_basis()
        self.sab_calculation_line_ids._normalize_section_membership()
        self._sab_validate_switchboard_structure()

        cabinets = self.sab_calculation_line_ids.filtered(
            lambda line: line.line_type == "cabinet"
        )
        if not cabinets:
            raise ValidationError(
                _(
                    "Für die Stücklistenerzeugung muss mindestens ein Schaltschrank, "
                    "z. B. UV1 oder QV1, angelegt und beendet sein."
                )
            )

        generated = self.env["sab.project.bom"]
        all_item_lines = self.env["sab.offer.calculation.line"]
        for cabinet in cabinets.sorted(key=lambda line: (line.sequence, line.id)):
            cabinet_items = self.sab_calculation_line_ids.filtered(
                lambda line: line.line_type == "item"
                and line.parent_cabinet_id == cabinet
            )
            if not cabinet_items:
                raise ValidationError(
                    _(f"Schaltschrank {cabinet.description} enthält keine Stücklistenpositionen.")
                )
            commands = self._sab_bom_values_for_lines(cabinet_items)
            if not commands:
                raise ValidationError(
                    _(
                        f"Für Schaltschrank {cabinet.description} konnten keine normalen "
                        "Materialpositionen erzeugt werden. Hilfsmaterial wird absichtlich "
                        "nicht in die Stückliste übernommen."
                    )
                )
            generated |= self._sab_prepare_or_update_bom(
                "cabinet", cabinet, commands
            )
            all_item_lines |= cabinet_items

        total_commands = self._sab_bom_values_for_lines(all_item_lines)
        generated |= self._sab_prepare_or_update_bom(
            "total", False, total_commands
        )

        stale = self.sab_bom_ids.filtered(
            lambda bom: bom.state == "draft"
            and bom.bom_scope == "cabinet"
            and bom.cabinet_line_id not in cabinets
        )
        deletable_stale = stale.filtered(
            lambda bom: not self._sab_bom_has_downstream_references(bom)
        )
        if deletable_stale:
            deletable_stale.unlink()

        return {
            "type": "ir.actions.act_window",
            "name": _("SAB-P Stücklisten"),
            "res_model": "sab.project.bom",
            "view_mode": "list,form",
            "domain": [("id", "in", generated.ids)],
            "target": "current",
        }
