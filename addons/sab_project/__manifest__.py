{
    "name": "SAB-P Projekt- und Angebotsnummern",
    "summary": "SAB-P Suite für Projekt, Kalkulation, Fertigung, Einkauf, Lager, Dokumente, Zeiterfassung, Nachkalkulation, Mitarbeiter-Mobile und Kundenportal",
    "version": "19.0.5.35.0",
    "category": "Services/Project",
    "author": "SAB-P GmbH",
    "license": "LGPL-3",
    "depends": ["auth_signup", "mail", "portal", "project", "sale_management"],
    "data": [
        "security/sab_security.xml", "security/ir.model.access.csv", "security/sab_record_rules.xml",
        "data/sab_classification_data.xml", "data/sab_calculation_sequence.xml", "data/sab_stock_sequence.xml", "data/sab_work_area_data.xml",
        "views/sab_menu_views.xml", "views/sab_employee_admin_views.xml", "views/sab_employee_confidential_views.xml",
        "views/sab_calculation_item_views.xml", "views/res_config_settings_views.xml", "views/project_project_views.xml",
        "views/project_customer_portal_views.xml", "views/sab_project_overview_views.xml", "views/sab_classification_views.xml",
        "views/sale_order_views.xml", "views/sab_manufacturer_views.xml", "views/sab_product_views.xml", "views/sab_supplier_views.xml",
        "views/sab_supplier_product_views.xml", "views/sab_calculation_change_log_views.xml", "views/sab_project_bom_views.xml",
        "views/sab_production_order_views.xml", "views/sab_purchase_requirement_views.xml", "views/sab_stock_movement_views.xml",
        "views/sab_project_document_views.xml", "views/sab_time_entry_views.xml", "views/sab_project_controlling_views.xml",
        "views/sab_employee_mobile_views.xml", "views/sab_employee_feedback_views.xml", "views/sab_customer_status_views.xml",
        "views/sab_customer_portal_templates.xml", "wizard/sab_calculation_import_views.xml", "wizard/sab_datanorm_import_views.xml"
    ],
    "installable": True,
    "application": False,
    "auto_install": False
}
