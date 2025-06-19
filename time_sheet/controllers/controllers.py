# -*- coding: utf-8 -*-
import json
import base64
from datetime import datetime
import cv2
import numpy as np

from odoo import http, fields
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class CameraController(http.Controller):

    @http.route('/camera/temp_recognize', type='http', auth='user', csrf=False, methods=['POST'])
    def temp_recognize(self, **kw):
        """
        Nhận POST raw JSON từ fetch():
            { "image": "<data:image/jpeg;base64,...>", "action_type": "in" }
        Trả về:
            { success: True|False, message: "...", user_id?, user_name? }
        """

        # 1) Đọc payload JSON
        try:
            data = request.jsonrequest
        except Exception as e:
            # fallback nếu jsonrequest không dùng được
            body = request.httprequest.data.decode('utf-8')
            try:
                data = json.loads(body)
            except Exception:
                _logger.error("❌ Không thể parse JSON payload: %s", e)
                return request.make_json_response({
                    'success': False,
                    'message': f'Invalid JSON payload: {e}'
                })

        image_data = data.get('image')
        action_type = data.get('action_type', 'in')

        if not image_data:
            _logger.error("❌ Không có ảnh được truyền lên! Payload: %s", data)
            return request.make_json_response({
                'success': False,
                'message': 'Không có ảnh được truyền lên.'
            })

        # Tách phần base64 nếu có prefix data:image/...
        if ',' in image_data:
            _, b64 = image_data.split(',', 1)
        else:
            b64 = image_data

        # 2) Decode ảnh
        try:
            img_bytes = base64.b64decode(b64)
            arr = np.frombuffer(img_bytes, np.uint8)
            img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except Exception as e:
            _logger.error("❌ Lỗi decode ảnh: %s", e)
            return request.make_json_response({
                'success': False,
                'message': f'Lỗi decode ảnh: {e}'
            })

        if img_bgr is None:
            return request.make_json_response({
                'success': False,
                'message': 'Ảnh không hợp lệ sau decode.'
            })

        # 3) Gọi service nhận diện
        try:
            service = request.env['face.recognition.service'].sudo()
            partner_id, _ = service.recognize_face(img_bgr)
        except Exception as e:
            _logger.exception("❌ Lỗi khi gọi recognize_face")
            return request.make_json_response({
                'success': False,
                'message': f'Lỗi nhận diện: {e}'
            })

        if not partner_id:
            return request.make_json_response({
                'success': False,
                'message': 'Không nhận diện được khuôn mặt.'
            })

        partner = request.env['res.partner'].sudo().browse(partner_id)
        if not partner:
            return request.make_json_response({
                'success': False,
                'message': 'Partner không tồn tại.'
            })

        # 4) Xử lý giờ vào / ra
        now_utc = datetime.utcnow()
        now_user = fields.Datetime.context_timestamp(request.env.user, now_utc)
        now_naive = now_user.replace(tzinfo=None)
        TimeSheet = request.env['time.sheet'].sudo()

        if action_type == 'in':
            vals = {
                'partner_id': partner.id,
                'time_in': now_naive,
                'time_out': False,
                'date': now_naive.date(),
                'image': b64,
            }
            try:
                TimeSheet.create(vals)
            except Exception as e:
                _logger.exception("❌ Lỗi tạo check-in")
                return request.make_json_response({
                    'success': False,
                    'message': f'Không thể tạo check-in: {e}'
                })
            return request.make_json_response({
                'success': True,
                'message': f'Check-in thành công cho {partner.name}',
                'user_id': partner.id,
                'user_name': partner.name,
            })

        else:  # action_type == 'out'
            today = now_naive.date()
            recs = TimeSheet.search([
                ('partner_id', '=', partner.id),
                ('date', '=', today),
                ('time_out', '=', False),
            ], order='time_in desc', limit=1)
            if not recs:
                return request.make_json_response({
                    'success': False,
                    'message': 'Không tìm thấy bản ghi check-in để check-out.'
                })
            try:
                recs.write({'time_out': now_naive})
            except Exception as e:
                _logger.exception("❌ Lỗi cập nhật check-out")
                return request.make_json_response({
                    'success': False,
                    'message': f'Không thể check-out: {e}'
                })
            return request.make_json_response({
                'success': True,
                'message': f'Check-out thành công cho {partner.name}',
                'user_id': partner.id,
                'user_name': partner.name,
            })
