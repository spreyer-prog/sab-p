from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SabCalculationComponentTemplate(models.Model):
    _name = "sab.calculation.component.template"
    _description = "SAB-P Kalkulationsbauteil"
    _order = "name, id"
    _rec_name = "name"

    name = fields.Char(string="Kalkulationsbauteil", required=True, index=True)
    active = fields.Boolean(string="Aktiv", default=True, index=True)
    note = fields.Text(string="Interne Hinweise")
    line_ids = fields.One2many(
        "sab.calculation.component.template.line",
        "template_id",
        string="Kalkulationspositionen",
        copy=True,
    )
    line_count = fields.Integer(string="Positionen", compute="_compute_line_count")
    source_project_id = fields.Many2one(
        "project.project",
        string="Erzeugt aus Projekt",
        readonly=True,
        copy=False,
        ondelete="set null",
        index=True,
    )
    source_order_id = fields.Many2one(
        "sale.order",
        string="Erzeugt aus Angebot",
        readonly=True,
        copy=False,
        ondelete="set null",
        index=True,
    )
    source_section_line_id = fields.Many2one(
        "sab.offer.calculation.line",
        string="Erzeugt aus Bauteil",
        readonly=True,
        copy=False,
        ondelete="set null",
        index=True,
    )

    _source_section_unique = models.Constraint(
        "UNIQUE(source_section_line_id)",
        "Dieses Angebotsbauteil ist bereits als Kalkulationsbauteil gespeichert.",
    )

    @api.depends("line_ids")
    def _compute_line_count(self):
        for template in self:
            template.line_count = len(template.line_ids)


class SabCalculationComponentTemplateLine(models.Model):
    _name = "sab.calculation.component.template.line"
    _description = "SAB-P Kalkulationsbauteil-Position"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "sab.calculation.component.template",
        string="Kalkulationsbauteil",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Pos.", default=10, index=True)
    calculation_item_id = fields.Many2one(
        "sab.calculation.item",
        string="Kalkulationsartikel",
        ondelete="restrict",
        index=True,
    )
    odoo_product_id = fields.Many2one(
        "product.product",
        string="Produkt",
        ondelete="restrict",
        index=True,
    )
    quantity = fields.Float(string="Menge", required=True, default=1.0, digits=(16, 3))
    description = fields.Text(string="Angebotstext")
    note = fields.Char(string="Bemerkung")

    @api.constrains("calculation_item_id", "odoo_product_id")
    def _check_source(self):
        for line in self:
            if bool(line.calculation_item_id) == bool(line.odoo_product_id):
                raise ValidationError(
                    "Eine Kalkulationsbauteil-Position benötigt genau einen "
                    "Kalkulationsartikel oder ein Produkt."
                )

    @api.constrains("quantity")
    def _check_quantity(self):
        for line in self:
            if line.quantity < 0:
                raise ValidationError("Die Menge darf nicht negativ sein.")


class SaleOrderOfferReuse(models.Model):
    _inherit = "sale.order"

    def _sab_offer_reuse_assert_editable(self):
        self.ensure_one()
        if not self.sab_project_id:
            raise ValidationError("Das Angebot benötigt ein SAB-P Projekt.")
        if self.state not in ("draft", "sent"):
            raise ValidationError(
                "Positionen können nur in einem Angebotsentwurf oder gesendeten Angebot ergänzt werden."
            )
        return True

    def _sab_offer_reuse_structure_state(self):
        self.ensure_one()
        current_cabinet = False
        current_section = False
        last_sequence = 0
        for line in self.sab_calculation_line_ids.sorted(key=lambda item: (item.sequence, item.id)):
            last_sequence = max(last_sequence, line.sequence or 0)
            if line.line_type == "cabinet":
                current_cabinet = line
                current_section = False
            elif line.line_type == "cabinet_end":
                current_cabinet = False
                current_section = False
            elif line.line_type == "section":
                current_section = line
            elif line.line_type == "section_end":
                current_section = False
        return current_cabinet, current_section, last_sequence + 10

    def _sab_offer_reuse_prepare_insertion(self, adding_component=False):
        self._sab_offer_reuse_assert_editable()
        cabinet, section, sequence = self._sab_offer_reuse_structure_state()
        if self.sab_calculation_source == "schematic" and not cabinet:
            raise ValidationError(
                "Bitte zuerst mit 'Schaltschrank erstellen' einen offenen Schaltschrank anlegen. "
                "Die übernommene Position muss eindeutig einem Verteiler zugeordnet werden."
            )
        if adding_component and section:
            raise ValidationError(
                f"Das Bauteil '{section.description or 'ohne Bezeichnung'}' ist noch offen. "
                "Bitte zuerst 'Bauteil beenden' verwenden."
            )
        return sequence

    def _sab_offer_reuse_create_lines(self, values_list):
        self.ensure_one()
        Line = self.env["sab.offer.calculation.line"].with_context(
            skip_section_normalize=True,
            skip_sale_line_sync=True,
        )
        prepared = []
        for incoming in values_list:
            values = dict(incoming)
            values["order_id"] = self.id
            prepared.append(values)
        created = Line.create(prepared)
        all_lines = self.env["sab.offer.calculation.line"].search(
            [("order_id", "=", self.id)], order="sequence, id"
        )
        if all_lines:
            all_lines._normalize_section_membership()
            all_lines._sync_customer_order_lines()
        return created

    @staticmethod
    def _sab_offer_reuse_item_values(source, sequence, keep_project_positions=True):
        values = {
            "line_type": "item",
            "sequence": sequence,
            "quantity": source.quantity or 0.0,
            "description": source.description or False,
            "note": source.note or False,
        }
        if source.calculation_item_id:
            values["calculation_item_id"] = source.calculation_item_id.id
        else:
            values["odoo_product_id"] = source.odoo_product_id.id
        if keep_project_positions:
            values.update(
                {
                    "lv_position": source.lv_position or False,
                    "is_ntg": bool(source.is_ntg),
                    "schematic_reference": source.schematic_reference or False,
                }
            )
        return values

    def _sab_offer_reuse_clone_project_component(self, source_section):
        self.ensure_one()
        sequence = self._sab_offer_reuse_prepare_insertion(adding_component=True)
        children = source_section.child_line_ids.filtered(
            lambda item: item.line_type == "item" and (item.calculation_item_id or item.odoo_product_id)
        ).sorted(key=lambda item: (item.sequence, item.id))
        if not children:
            raise ValidationError("Das ausgewählte Bauteil enthält keine wiederverwendbaren Positionen.")

        values_list = [
            {
                "line_type": "section",
                "sequence": sequence,
                "description": source_section.description,
                "lv_position": source_section.lv_position or False,
                "is_ntg": bool(source_section.is_ntg),
                "schematic_reference": source_section.schematic_reference or False,
                "note": source_section.note or False,
            }
        ]
        for child in children:
            sequence += 10
            values_list.append(
                self._sab_offer_reuse_item_values(
                    child,
                    sequence,
                    keep_project_positions=True,
                )
            )
        sequence += 10
        values_list.append({"line_type": "section_end", "sequence": sequence})
        return self._sab_offer_reuse_create_lines(values_list)

    def _sab_offer_reuse_add_template(self, template):
        self.ensure_one()
        sequence = self._sab_offer_reuse_prepare_insertion(adding_component=True)
        template_lines = template.line_ids.sorted(key=lambda item: (item.sequence, item.id))
        if not template_lines:
            raise ValidationError("Das Kalkulationsbauteil enthält keine Positionen.")

        values_list = [
            {
                "line_type": "section",
                "sequence": sequence,
                "description": template.name,
                "note": template.note or False,
            }
        ]
        for template_line in template_lines:
            sequence += 10
            values = {
                "line_type": "item",
                "sequence": sequence,
                "quantity": template_line.quantity,
                "description": template_line.description or False,
                "note": template_line.note or False,
            }
            if template_line.calculation_item_id:
                values["calculation_item_id"] = template_line.calculation_item_id.id
            else:
                values["odoo_product_id"] = template_line.odoo_product_id.id
            values_list.append(values)
        sequence += 10
        values_list.append({"line_type": "section_end", "sequence": sequence})
        return self._sab_offer_reuse_create_lines(values_list)

    def sab_offer_reuse_payload(self):
        self.ensure_one()
        if not self.sab_project_id:
            return {
                "editable": False,
                "project": False,
                "lv_positions": [],
                "project_components": [],
                "library_components": [],
            }

        Mapping = self.env["sab.project.lv.mapping"]
        mappings = Mapping.search(
            [("project_id", "=", self.sab_project_id.id)],
            order="is_ntg, ntg_number, position_code, id",
            limit=500,
        )
        lv_positions = []
        for mapping in mappings:
            source = mapping.calculation_item_id or mapping.odoo_product_id
            lv_positions.append(
                {
                    "id": mapping.id,
                    "position": mapping.position_code,
                    "is_ntg": bool(mapping.is_ntg),
                    "source_type": "Kalkulationsartikel" if mapping.calculation_item_id else "Produkt",
                    "source_name": source.display_name if source else "",
                    "first_offer": mapping.first_order_id.sab_offer_reference
                    or mapping.first_order_id.name
                    or "",
                }
            )

        Section = self.env["sab.offer.calculation.line"]
        sections = Section.search(
            [
                ("order_id.sab_project_id", "=", self.sab_project_id.id),
                ("order_id.state", "!=", "cancel"),
                ("line_type", "=", "section"),
            ],
            order="order_id desc, sequence, id",
            limit=300,
        )
        Template = self.env["sab.calculation.component.template"]
        templates_by_source = {
            template.source_section_line_id.id: template
            for template in Template.search(
                [("source_section_line_id", "in", sections.ids)],
                order="id",
            )
            if template.source_section_line_id
        }
        project_components = []
        for section in sections:
            children = section.child_line_ids.filtered(
                lambda item: item.line_type == "item" and (item.calculation_item_id or item.odoo_product_id)
            ).sorted(key=lambda item: (item.sequence, item.id))
            if not children:
                continue
            positions = []
            for code in [section.lv_position] + children.mapped("lv_position"):
                code = (code or "").strip()
                if code and code not in positions:
                    positions.append(code)
            saved_template = templates_by_source.get(section.id)
            project_components.append(
                {
                    "id": section.id,
                    "name": section.description or "Bauteil ohne Bezeichnung",
                    "offer": section.order_id.sab_offer_reference or section.order_id.name,
                    "is_current": section.order_id == self,
                    "positions": ", ".join(positions),
                    "line_count": len(children),
                    "total": section.section_total or 0.0,
                    "saved_template_id": saved_template.id if saved_template else False,
                    "saved_template_name": saved_template.name if saved_template else "",
                }
            )
        project_components.sort(
            key=lambda item: (
                0 if item["is_current"] else 1,
                item["offer"],
                item["name"],
            )
        )

        library_components = []
        for template in Template.search([("active", "=", True)], order="name, id", limit=300):
            library_components.append(
                {
                    "id": template.id,
                    "name": template.name,
                    "line_count": template.line_count,
                    "source_project": template.source_project_id.display_name
                    if template.source_project_id
                    else "",
                    "source_offer": template.source_order_id.sab_offer_reference
                    or template.source_order_id.name
                    or "",
                }
            )

        return {
            "editable": self.state in ("draft", "sent"),
            "project": self.sab_project_id.display_name,
            "offer": self.sab_offer_reference or self.name,
            "calculation_source": self.sab_calculation_source,
            "lv_positions": lv_positions,
            "project_components": project_components,
            "library_components": library_components,
        }

    def sab_offer_add_reuse_entry(self, entry_kind, entry_id):
        self.ensure_one()
        self._sab_offer_reuse_assert_editable()
        entry_id = int(entry_id)

        if entry_kind == "lv":
            mapping = self.env["sab.project.lv.mapping"].browse(entry_id).exists()
            if not mapping or mapping.project_id != self.sab_project_id:
                raise ValidationError("Die ausgewählte LV-/NTG-Position gehört nicht zu diesem Projekt.")
            sequence = self._sab_offer_reuse_prepare_insertion(adding_component=False)
            values = {
                "line_type": "item",
                "sequence": sequence,
                "quantity": 1.0,
            }
            if mapping.calculation_item_id:
                values["calculation_item_id"] = mapping.calculation_item_id.id
            else:
                values["odoo_product_id"] = mapping.odoo_product_id.id
            self._sab_offer_reuse_create_lines([values])
            message = f"LV-/NTG-Position {mapping.position_code} wurde übernommen."

        elif entry_kind == "project_component":
            section = self.env["sab.offer.calculation.line"].browse(entry_id).exists()
            if (
                not section
                or section.line_type != "section"
                or section.order_id.sab_project_id != self.sab_project_id
                or section.order_id.state == "cancel"
            ):
                raise ValidationError("Das ausgewählte Projektbauteil ist nicht verfügbar.")
            self._sab_offer_reuse_clone_project_component(section)
            message = f"Bauteil {section.description or ''} wurde vollständig übernommen."

        elif entry_kind == "library_component":
            template = self.env["sab.calculation.component.template"].browse(entry_id).exists()
            if not template or not template.active:
                raise ValidationError("Das ausgewählte Kalkulationsbauteil ist nicht verfügbar.")
            self._sab_offer_reuse_add_template(template)
            message = f"Kalkulationsbauteil {template.name} wurde übernommen."

        else:
            raise ValidationError("Unbekannte Übernahmeart.")

        return {"message": message}

    def sab_offer_save_component_template(self, section_line_id):
        self.ensure_one()
        if not self.sab_project_id:
            raise ValidationError("Das Angebot benötigt ein SAB-P Projekt.")
        section = self.env["sab.offer.calculation.line"].browse(int(section_line_id)).exists()
        if (
            not section
            or section.line_type != "section"
            or section.order_id.sab_project_id != self.sab_project_id
            or section.order_id.state == "cancel"
        ):
            raise ValidationError("Das ausgewählte Projektbauteil ist nicht verfügbar.")

        children = section.child_line_ids.filtered(
            lambda item: item.line_type == "item" and (item.calculation_item_id or item.odoo_product_id)
        ).sorted(key=lambda item: (item.sequence, item.id))
        if not children:
            raise ValidationError("Das Bauteil enthält keine wiederverwendbaren Kalkulationspositionen.")

        line_commands = [(5, 0, 0)]
        for sequence, child in enumerate(children, start=1):
            values = {
                "sequence": sequence * 10,
                "quantity": child.quantity,
                "description": child.description or False,
                "note": child.note or False,
            }
            if child.calculation_item_id:
                values["calculation_item_id"] = child.calculation_item_id.id
            else:
                values["odoo_product_id"] = child.odoo_product_id.id
            line_commands.append((0, 0, values))

        Template = self.env["sab.calculation.component.template"]
        template = Template.search([("source_section_line_id", "=", section.id)], limit=1)
        values = {
            "name": (section.description or "Kalkulationsbauteil").strip(),
            "active": True,
            "source_project_id": section.order_id.sab_project_id.id,
            "source_order_id": section.order_id.id,
            "source_section_line_id": section.id,
            "line_ids": line_commands,
        }
        if template:
            template.write(values)
            verb = "aktualisiert"
        else:
            template = Template.create(values)
            verb = "in die Kalkulationsdatenbank übernommen"

        # LV-/NTG-Positionen und Schaltplanreferenzen werden bewusst nicht im
        # Kalkulationsbauteil gespeichert. Sie bleiben immer projektbezogen.
        return {
            "template_id": template.id,
            "template_name": template.name,
            "message": f"Bauteil {template.name} wurde {verb} – ohne LV-/NTG-Position.",
        }
