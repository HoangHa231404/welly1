from odoo import models

class CameraWizard(models.TransientModel):
    _name = 'camera.wizard'
    _description = 'Wizard chụp ảnh người dùng'

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}

