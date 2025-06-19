# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import json
import numpy as np
import face_recognition

class ResPartner(models.Model):
    _inherit = "res.partner"

    photo_ids = fields.One2many(
        comodel_name="res.partner.photo",
        inverse_name="partner_id",
        string="Ảnh đăng ký",
    )
    face_descriptor = fields.Text(string="Face Descriptor")  # Lưu dưới dạng JSON

    def save_face_descriptor(self, descriptor):
        """Lưu descriptor (numpy array hoặc list) vào partner.face_descriptor."""
        if descriptor is not None:
            if isinstance(descriptor, (list, np.ndarray)):
                # nếu là numpy array, chuyển về list
                data = descriptor.tolist() if isinstance(descriptor, np.ndarray) else descriptor
                self.face_descriptor = json.dumps(data)
            else:
                raise ValidationError("Descriptor phải là numpy array hoặc danh sách")
        else:
            self.face_descriptor = None

    def face_recognition_compare(self, unknown_descriptor, tolerance=0.45):
        """
        So sánh unknown_descriptor (list hoặc numpy array) với các face_descriptor đã lưu.
        Trả về (partner, True) nếu match, hoặc (None, False) nếu không match.
        """
        if not unknown_descriptor:
            return None, False
        # Lấy tất cả partner có face_descriptor khác False
        partners = self.search([("face_descriptor", "!=", False)])
        known_faces = []
        for partner in partners:
            if partner.face_descriptor:
                try:
                    arr = np.array(json.loads(partner.face_descriptor), dtype=np.float32)
                    known_faces.append(arr)
                except Exception:
                    continue
        if not known_faces:
            return None, False
        # Gọi face_recognition.compare_faces (nếu cài face_recognition)
        if isinstance(unknown_descriptor, np.ndarray):
            target = unknown_descriptor
        else:
            target = np.array(unknown_descriptor, dtype=np.float32)
        results = face_recognition.compare_faces(known_faces, target, tolerance=tolerance)
        for idx, matched in enumerate(results):
            if matched:
                return partners[idx], True
        return None, False