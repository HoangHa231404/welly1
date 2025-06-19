from odoo import models, fields

class PartnerPhoto(models.Model):
    _name = 'res.partner.photo'
    _description = 'Ảnh đăng ký người dùng'

    partner_id = fields.Many2one('res.partner', string='Người dùng', ondelete='cascade', required=True)
    image = fields.Binary(string='Ảnh đăng ký', max_width=1024, max_height=1024)
    description = fields.Char(string="Ghi chú")
    capture_time = fields.Datetime(string="Thời gian đăng ký", default=fields.Datetime.now)
