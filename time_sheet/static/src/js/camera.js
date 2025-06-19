document.addEventListener('DOMContentLoaded', function () {
    odoo.define('time_sheet.camera', function (require) {
        "use strict";

        const rpc = require('web.rpc');
        let stream = null;
        let lastRecognizeResult = null;

        async function loadModels() {
            try {
                await Promise.all([
                    faceapi.nets.tinyFaceDetector.loadFromUri('/time_sheet/static/src/models/tiny_face_detector'),
                    faceapi.nets.faceLandmark68Net.loadFromUri('/time_sheet/static/src/models/face_landmark_68'),
                    faceapi.nets.faceRecognitionNet.loadFromUri('/time_sheet/static/src/models/face_recognition')
                ]);
                console.log("✅ Mô hình nhận diện đã được tải thành công");
            } catch (err) {
                console.error("❌ Lỗi khi tải mô hình nhận diện:", err);
            }
        }

        async function startCamera(videoId = 'wizard_camera_stream') {
            lastRecognizeResult = null;
            document.querySelectorAll('canvas').forEach(c => c.remove());
            const video = document.getElementById(videoId);
            if (!video) return console.error("Không tìm thấy video:", videoId);
            try {
                stream = await navigator.mediaDevices.getUserMedia({ video: true });
                video.srcObject = stream;
                await video.play();
                console.log("✅ Camera đã được bật");
            } catch (err) {
                console.error("❌ Không thể mở camera:", err);
            }
        }

        function stopCamera(videoId = 'wizard_camera_stream') {
            const video = document.getElementById(videoId);
            if (stream) {
                stream.getTracks().forEach(t => t.stop());
                stream = null;
                console.log("✅ Camera đã được tắt");
            }
            if (video) {
                video.pause();
            }
            if (lastRecognizeResult && lastRecognizeResult.success) {
                alert(`👤 Người dùng: ${lastRecognizeResult.user_name}`);
            } else {
                alert("❌ Không có người dùng nào được nhận diện.");
            }
        }

        async function captureAndRecognize(videoId = 'wizard_camera_stream') {
            lastRecognizeResult = null;
            const video = document.getElementById(videoId);
            if (!video || video.videoWidth === 0) return console.error("Video không sẵn sàng để chụp");
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext('2d').drawImage(video, 0, 0);
            const imageData = canvas.toDataURL('image/jpeg');

            try {
                const detection = await faceapi.detectSingleFace(canvas, new faceapi.TinyFaceDetectorOptions())
                    .withFaceLandmarks()
                    .withFaceDescriptor();
                if (!detection) {
                    alert("❌ Không phát hiện được khuôn mặt");
                    return;
                }
                const result = await rpc.query({
                    route: '/camera/temp_recognize',
                    params: { image: imageData, action_type: 'in' }
                });
                lastRecognizeResult = result;
                if (result.success) {
                    alert(`✅ Nhận diện thành công: ${result.user_name}`);
                } else {
                    alert(`❌ Nhận diện thất bại: ${result.message}`);
                }
            } catch (err) {
                console.error("❌ Lỗi khi nhận diện khuôn mặt:", err);
            }
        }

        async function recognizeFace(type = 'in', videoId = 'wizard_camera_stream') {
            const video = document.getElementById(videoId);
            if (!video || video.videoWidth === 0) {
                return alert("Video không sẵn sàng để quét");
            }
            // Chụp ảnh
            const canvas = document.createElement("canvas");
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext("2d").drawImage(video, 0, 0);
            const imageData = canvas.toDataURL("image/jpeg");

            try {
                const response = await fetch("/camera/temp_recognize", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        image: imageData,
                        action_type: type    // <-- dùng biến `type` ở đây
                    })
                });
                const data = await response.json();
                console.log("🎯 Kết quả:", data);
                alert(data.message);
            } catch (error) {
                console.error("❌ Lỗi không xác định từ server", error);
                alert("Lỗi không xác định từ server");
            }
        }

        document.body.addEventListener('click', function (e) {
            if (e.target.classList.contains('o_camera_btn_start')) {
                startCamera();
            }
            if (e.target.classList.contains('o_camera_btn_stop')) {
                stopCamera();
            }
            if (e.target.classList.contains('o_camera_btn_capture')) {
                captureAndRecognize();
            }
            if (e.target.classList.contains('o_camera_btn_checkin')) {
                recognizeFace('in');
            }
            if (e.target.classList.contains('o_camera_btn_checkout')) {
                recognizeFace('out');
            }
        });

        loadModels();

        return {
            startCamera,
            stopCamera,
            captureAndRecognize,
            recognizeFace,
        };
    });
});
