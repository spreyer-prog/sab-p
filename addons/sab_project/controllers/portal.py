import base64
import mimetypes

from odoo import http
from odoo.http import request
from werkzeug.exceptions import NotFound


class SabCustomerPortal(http.Controller):

    def _portal_partner(self):
        return request.env.user.partner_id.commercial_partner_id

    def _status_for_current_customer(self, status_id):
        partner = self._portal_partner()
        status = request.env["sab.customer.project.status"].sudo().browse(status_id).exists()
        if not status or not status.is_portal_visible_to(partner):
            raise NotFound()
        return status

    @http.route("/my/sab-projects", type="http", auth="user", methods=["GET"])
    def sab_projects(self, **kwargs):
        partner = self._portal_partner()
        statuses = request.env["sab.customer.project.status"].sudo().search([
            ("released", "=", True),
            ("partner_id.commercial_partner_id", "=", partner.id),
        ], order="project_id desc")
        return request.render("sab_project.portal_sab_projects", {
            "statuses": statuses,
            "page_name": "sab_projects",
        })

    @http.route("/my/sab-projects/<int:status_id>", type="http", auth="user", methods=["GET"])
    def sab_project_detail(self, status_id, **kwargs):
        status = self._status_for_current_customer(status_id)
        project = status.project_id
        documents = request.env["sab.project.document"].sudo().search([
            ("project_id", "=", project.id),
            ("state", "=", "released"),
            ("customer_visible", "=", True),
        ], order="document_type, name, version desc")
        photos = request.env["sab.employee.feedback"].sudo().search([
            ("project_id", "=", project.id),
            ("feedback_type", "=", "photo"),
            ("state", "=", "processed"),
            ("customer_visible", "=", True),
        ], order="create_date desc")
        return request.render("sab_project.portal_sab_project_detail", {
            "status": status,
            "project": project,
            "documents": documents,
            "photos": photos,
            "page_name": "sab_project_detail",
        })

    @http.route("/my/sab-document/<int:document_id>/download", type="http", auth="user", methods=["GET"])
    def sab_document_download(self, document_id, **kwargs):
        partner = self._portal_partner()
        document = request.env["sab.project.document"].sudo().browse(document_id).exists()
        if not document or not document.is_portal_visible_to(partner):
            raise NotFound()
        payload = base64.b64decode(document.file_data or b"")
        mimetype = mimetypes.guess_type(document.file_name or "")[0] or "application/octet-stream"
        filename = (document.file_name or "dokument").replace('"', "")
        return request.make_response(payload, headers=[
            ("Content-Type", mimetype),
            ("Content-Disposition", f'attachment; filename="{filename}"'),
        ])

    @http.route("/my/sab-photo/<int:feedback_id>", type="http", auth="user", methods=["GET"])
    def sab_photo(self, feedback_id, **kwargs):
        partner = self._portal_partner()
        feedback = request.env["sab.employee.feedback"].sudo().browse(feedback_id).exists()
        if not feedback or not feedback.is_portal_visible_to(partner):
            raise NotFound()
        payload = base64.b64decode(feedback.photo or b"")
        mimetype = mimetypes.guess_type(feedback.photo_filename or "")[0] or "image/jpeg"
        return request.make_response(payload, headers=[
            ("Content-Type", mimetype),
            ("Cache-Control", "private, max-age=300"),
        ])
