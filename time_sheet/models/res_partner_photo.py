# -*- coding: utf-8 -*-
from odoo import models, fields

class ResPartnerPhoto(models.Model):
    _name = 'res.partner.photo'
    _description = 'Ảnh khuôn mặt của partner'

    partner_id = fields.Many2one('res.partner', string="Partner", required=True)
    image      = fields.Binary(string="Image", attachment=True, required=True)
    description = fields.Char(string="Mô tả")
    capture_time = fields.Datetime(string="Thời gian")


