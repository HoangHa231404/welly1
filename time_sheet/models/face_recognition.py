# -*- coding: utf-8 -*-
from odoo import models, fields, api
import os
import tempfile
import base64
import json
import logging
import numpy as np
import cv2
from deepface import DeepFace
import faiss
from PIL import Image
import io

_logger = logging.getLogger(__name__)


class FaceRecognitionService(models.AbstractModel):
    _name = "face.recognition.service"
    _description = "Face Recognition Service (DeepFace + FAISS)"

    VECTOR_SIZE = 128
    # Khởi tạo FAISS index (Inner Product) 128 chiều
    _faiss_index = faiss.IndexFlatIP(VECTOR_SIZE)
    _id_list = []  # danh sách IDs song song với vectors trong index

    @api.model
    def clear_index(self):
        """Xóa FAISS index và danh sách partner IDs."""
        FaceRecognitionService._faiss_index = faiss.IndexFlatIP(self.VECTOR_SIZE)
        self._id_list.clear()
        _logger.info("FAISS index has been fully reset.")

    @api.model
    def _compute_embedding(self, img_rgb_uint8):
        """
        Dùng DeepFace.represent để tính embedding (128-d, numpy float32):
        - img_rgb_uint8: numpy array RGB uint8 đã crop (face).
        """
        # Gọi trực tiếp represent từ ảnh numpy thay vì ghi ra file
        rep = DeepFace.represent(
            img_path=img_rgb_uint8,
            model_name="Facenet",
            enforce_detection=False  # Bởi vì bạn đã detect trước đó rồi
        )
        emb = np.array(rep[0]["embedding"], dtype=np.float32)
        emb = emb / np.linalg.norm(emb)
        return emb

    @api.model
    def register_partner_faces(self):
        """
        Duyệt qua tất cả res.partner.photo có ảnh, decode, detect bằng DeepFace, compute embedding,
        lưu descriptor về partner.face_descriptor (JSON) và add embedding vào FAISS index.
        """
        self.clear_index()
        Photo = self.env["res.partner.photo"].sudo()
        all_photos = Photo.search([("image", "!=", False)])
        if not all_photos:
            _logger.info("No partner.photo found to register.")
            return

        for photo in all_photos:
            partner = photo.partner_id
            raw_data = photo.image   # đây luôn là str Base64 trên Odoo

            # 1) Loại bỏ header data URI nếu có, rồi decode Base64 thành bytes
            try:
                if isinstance(raw_data, str) and ',' in raw_data:
                    # dạng "data:image/jpeg;base64,/9j/4AAQ..."
                    _, b64data = raw_data.split(',', 1)
                else:
                    b64data = raw_data
                img_bytes = base64.b64decode(b64data)
            except Exception as e:
                _logger.warning(f"[register_partner_faces] Base64 decode failed for partner_id={partner.id}: {e}")
                continue

            # 2) Giải mã bytes thành ảnh BGR
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            img_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if img_bgr is None:
                _logger.warning(f"[register_partner_faces] cv2.imdecode returned None for partner_id={partner.id}")
                continue

            # 3) Detect & crop face bằng DeepFace
            try:
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    cv2.imwrite(tmp.name, img_bgr)
                    path = tmp.name
                faces = DeepFace.extract_faces(
                    img_path=path,
                    detector_backend="mtcnn",
                    enforce_detection=True
                )
            except Exception as e:
                _logger.warning(f"[register_partner_faces] DeepFace detect failed for partner_id={partner.id}: {e}")
                faces = []
            finally:
                if os.path.exists(path):
                    os.remove(path)

            if not faces:
                _logger.warning(f"[register_partner_faces] No face detected for partner_id={partner.id}")
                continue

            # 4) Tính embedding
            face_rgb = faces[0]["face"].astype(np.uint8)
            try:
                emb = self._compute_embedding(face_rgb)
            except Exception as e:
                _logger.warning(f"[register_partner_faces] Compute embedding failed for partner_id={partner.id}: {e}")
                continue

            # 5) Lưu descriptor và thêm vào FAISS
            partner.sudo().write({"face_descriptor": json.dumps(emb.tolist())})
            self._faiss_index.add(emb.reshape(1, -1))
            self._id_list.append(partner.id)
            _logger.info(f"[register_partner_faces] Registered partner_id={partner.id}")

        _logger.info(f"[register_partner_faces] Total faces indexed: {self._faiss_index.ntotal}")

    @api.model
    def recognize_face(self, image_np, threshold=0.7, tolerance=0.6):
        """
        Nhận diện khuôn mặt từ ảnh numpy.ndarray (BGR).
        - Nếu FAISS index đang rỗng, tự động gọi register_partner_faces() đầu tiên.
        - Trả về (partner_id, image_np) nếu tìm thấy match threshold, ngược lại (None, image_np).
        """
        # Nếu chưa index, auto tạo index
        if self._faiss_index.ntotal == 0:
            _logger.info("recognize_face: FAISS index is empty, calling register_partner_faces().")
            self.register_partner_faces()

        # Kiểm tra input
        if not isinstance(image_np, np.ndarray) or image_np.size == 0:
            _logger.warning("recognize_face: Input image invalid")
            return None, image_np

        # Detect & crop face với DeepFace
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                cv2.imwrite(tmp.name, image_np)
                path = tmp.name
            faces = DeepFace.extract_faces(img_path=path, detector_backend="mtcnn", enforce_detection=True)
        except Exception as e:
            _logger.error(f"recognize_face: DeepFace detection error: {e}")
            faces = []
        finally:
            if os.path.exists(path):
                os.remove(path)

        if not faces:
            _logger.info("recognize_face: No face detected.")
            return None, image_np

        face_rgb = faces[0]["face"].astype(np.uint8)
        # Tính embedding
        try:
            emb = self._compute_embedding(face_rgb)
        except Exception as e:
            _logger.error(f"recognize_face: error compute embedding: {e}")
            return None, image_np

        # So sánh FAISS
        n = self._faiss_index.ntotal
        if n > 0:
            D, I = self._faiss_index.search(emb.reshape(1, -1), 1)
            score = float(D[0][0])
            idx = int(I[0][0])
            pid = self._id_list[idx]
            if score >= threshold:
                partner = self.env["res.partner"].browse(pid)
                _logger.info(f"recognize_face: FAISS match partner_id={pid}, score={score}")
                return pid, image_np
            else:
                _logger.info(f"recognize_face: FAISS no match (score={score})")

        # Nếu chưa match FAISS, trả về None
        _logger.info("recognize_face: No match found.")
        return None, image_np

    @api.model
    def recognize_face_base64(self, image_base64, threshold=0.7, tolerance=0.6):
        """
        Nếu controller gửi base64, decode thành numpy BGR rồi gọi recognize_face(...)
        """
        header, b64_data = image_base64.split(",", 1)
        image_bytes = base64.b64decode(b64_data)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        rgb = np.array(image).astype(np.uint8)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        return self.recognize_face(bgr, threshold=threshold, tolerance=tolerance)

    @api.model
    def test_print_faiss_status(self):
        print(self.env['face.recognition.service']._faiss_index.ntotal)
        print(self.env['face.recognition.service']._id_list)
