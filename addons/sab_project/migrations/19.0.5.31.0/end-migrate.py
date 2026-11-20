import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Enrich existing production steps after introduction of SAB-P employee profiles.

    Existing technical user assignments are preserved. Where a matching SAB-P
    employee profile already exists, the employee link is added. Known legacy
    production step names receive the corresponding work area.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    Step = env["sab.production.step"].sudo()
    legacy_steps = Step.search([
        "|",
        ("work_area_id", "=", False),
        "&",
        ("responsible_user_id", "!=", False),
        ("responsible_employee_id", "=", False),
    ])
    if legacy_steps:
        legacy_steps.action_migrate_legacy_assignment()
        _logger.info("SAB-P migration: checked %s legacy production steps", len(legacy_steps))
