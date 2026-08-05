{
    "name": "SAB-P Projekt- und Angebotsnummern",
    "summary": "Eindeutige und konfigurierbare Projekt- und Angebotsnummern für SAB-P",
    "version": "19.0.2.0.0",
    "category": "Services/Project",
    "author": "SAB-P GmbH",
    "license": "LGPL-3",
    "depends": [
        "project",
        "sale_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/project_project_views.xml",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
