{
    "name": "SAB-P Projekt- und Angebotsnummern",
    "summary": "Projektübersicht, Statusfarben und konfigurierbare Nummern für SAB-P",
    "version": "19.0.4.0.0",
    "category": "Services/Project",
    "author": "SAB-P GmbH",
    "license": "LGPL-3",

    "depends": [
        "project",
        "sale_management",
    ],

    "data": [
        "security/ir.model.access.csv",

        "data/sab_classification_data.xml",
        "data/sab_calculation_sequence.xml",
        "data/sab_default_language.xml",

        "views/sab_menu_views.xml",
        "views/sab_calculation_item_views.xml",
        "views/res_config_settings_views.xml",
        "views/project_project_views.xml",
        "views/sab_project_overview_views.xml",
        "views/sab_classification_views.xml",
        "views/sale_order_views.xml",
        "views/sab_manufacturer_views.xml",
        "views/sab_product_views.xml",
        "views/sab_supplier_views.xml",
        "views/sab_supplier_product_views.xml",

        "wizard/sab_calculation_import_views.xml",
    ],

    "installable": True,
    "application": False,
    "auto_install": False,
}