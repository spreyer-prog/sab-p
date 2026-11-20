from .test_standard_purchase_bridge import TestSabStandardPurchaseBridge


def _test_total_bom_release_is_enough_for_procurement_handover(self):
    cabinet_bom, total_bom, package, requirement = (
        self._create_released_package(cabinet_released=False)
    )
    self.assertEqual(total_bom.state, "released")
    self.assertEqual(cabinet_bom.state, "released")
    self.assertEqual(package.state, "released")
    self.assertEqual(requirement.source_cabinet_bom_id, cabinet_bom)
    self.assertEqual(
        requirement.source_cabinet_line_id.bom_id,
        cabinet_bom,
    )


# Die Gesamtstückliste ist jetzt der einzige Freigabepunkt. Deshalb muss der
# frühere Test, der eine weiterhin offene Verteilerstückliste erwartet hat, auf
# die neue verbindliche Fachlogik aktualisiert werden.
TestSabStandardPurchaseBridge.test_total_bom_release_is_enough_for_procurement_handover = (
    _test_total_bom_release_is_enough_for_procurement_handover
)
