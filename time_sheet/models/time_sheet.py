# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class TimeSheet(models.Model):
    _name = "time.sheet"
    _description = "Time Sheet"

    partner_id = fields.Many2one(
        comodel_name="res.partner", string="Partner", required=True
    )
    time_in = fields.Datetime(string="Time In", required=True)
    time_out = fields.Datetime(string="Time Out")
    date = fields.Date(
        string="Date", default=fields.Date.context_today, required=True
    )
    image = fields.Binary(string="Image", attachment=True)

    @api.constrains("time_in", "time_out")
    def _check_time_out_greater_than_time_in(self):
        for record in self:
            if record.time_out and record.time_in and record.time_out < record.time_in:
                raise ValidationError(
                    "Giờ ra (Time Out) không thể nhỏ hơn giờ vào (Time In)."
                )

