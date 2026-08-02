/* 门诊失物招领系统 - 公共脚本 */

/* ===== HTML 转义（防注入，所有页面通用）===== */
function escapeHtml(s){
    if(s==null) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
                    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ===== 消息提示（轻量，替代 alert）===== */
function toast(msg, type) {
    type = type || "info";
    var colors = {
        success: "#2e7d32", error: "#c62828", info: "#2E7D9B", warn: "#f57c00"
    };
    var el = document.createElement("div");
    el.textContent = msg;
    el.style.cssText =
        "position:fixed;top:20px;left:50%;transform:translateX(-50%);" +
        "background:" + (colors[type] || colors.info) + ";color:#fff;padding:12px 24px;" +
        "border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,.2);z-index:9999;" +
        "font-size:15px;";
    document.body.appendChild(el);
    setTimeout(function () {
        el.style.transition = "opacity .4s";
        el.style.opacity = "0";
        setTimeout(function () { el.remove(); }, 400);
    }, 2500);
}

/* ===== 拍照功能（登记页用）===== */
var cameraStream = null;

function openCamera(videoId) {
    var video = document.getElementById(videoId);
    if (!video) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        toast("当前浏览器不支持摄像头，请改用上传图片。", "warn");
        return;
    }
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
        .then(function (stream) {
            cameraStream = stream;
            video.srcObject = stream;
            video.style.display = "block";
            video.play();
        })
        .catch(function (err) {
            toast("无法打开摄像头：" + (err.message || err.name) + "，可改用上传图片。", "warn");
        });
}

function stopCamera() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(function (t) { t.stop(); });
        cameraStream = null;
    }
}

/* 抓拍当前画面 → 写入隐藏字段 + 预览 */
function capturePhoto(videoId, previewId, hiddenId) {
    var video = document.getElementById(videoId);
    var preview = document.getElementById(previewId);
    var hidden = document.getElementById(hiddenId);
    if (!video || !video.videoWidth) {
        toast("摄像头还没准备好，请稍候。", "warn");
        return;
    }
    var canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    var dataUrl = canvas.toDataURL("image/jpeg", 0.85);
    hidden.value = dataUrl;
    preview.src = dataUrl;
    preview.style.display = "block";
    // 清空文件选择（避免混用）
    var fileInput = document.getElementById(hiddenId.replace("_data", "_file"));
    if (fileInput) fileInput.value = "";
    stopCamera();
    video.style.display = "none";
    toast("已拍照，记得点下方提交。", "success");
}

/* 上传图片预览 */
function previewFile(input, previewId, hiddenId) {
    var file = input.files[0];
    if (!file) return;
    var preview = document.getElementById(previewId);
    var hidden = document.getElementById(hiddenId);
    var reader = new FileReader();
    reader.onload = function (e) {
        preview.src = e.target.result;
        preview.style.display = "block";
    };
    reader.readAsDataURL(file);
    hidden.value = ""; // 上传文件时清空拍照数据
    // 停掉摄像头
    stopCamera();
    var v = document.getElementById(input.id.replace("_file", "_video"));
    if (v) v.style.display = "none";
}

/* ===== 拍照/上传 切换 tab ===== */
function switchPhotoTab(tab, groupName) {
    var camBox = document.getElementById(groupName + "_camera");
    var upBox = document.getElementById(groupName + "_upload");
    var tabs = document.querySelectorAll("[data-tab-group='" + groupName + "']");
    tabs.forEach(function (t) { t.classList.remove("active"); });
    tab.classList.add("active");
    if (tab.dataset.tab === "camera") {
        camBox.style.display = "block";
        upBox.style.display = "none";
        openCamera(groupName + "_video");
    } else {
        camBox.style.display = "none";
        upBox.style.display = "block";
        stopCamera();
    }
}

/* ===== 下拉“其他”联动 ===== */
function toggleOther(select, otherId) {
    var other = document.getElementById(otherId);
    other.style.display = (select.value === "__other__") ? "block" : "none";
}

/* ===== 详情弹窗（列表页点行用）===== */
function showDetail(itemId) {
    fetch("/api/item/" + itemId).then(function (r) { return r.json(); })
        .then(function (data) {
            if (!data.ok) { toast("读取失败", "error"); return; }
            var it = data.item;
            var photoHtml = it.photo
                ? '<img class="photo-big" src="/uploads/' + it.photo + '">'
                : '<div style="color:#999;margin:10px 0;">（无照片）</div>';
            var claimHtml = it.status === "已认领"
                ? '<div style="margin-top:14px;padding-top:12px;border-top:1px dashed #ccc;">' +
                  '<strong>认领信息</strong><br>' +
                  '认领人：' + (it.claimer_name || "") + '　' +
                  '电话：' + (it.claimer_phone || "") + '<br>' +
                  '认领时间：' + (it.claimed_at || "") + '　' +
                  '经办人：' + (it.operator || "") + '<br>' +
                  '特征已核实：' + (it.feature_verified ? "是" : "否") +
                  (it.claimer_photo
                      ? '<br><span class="k">认领人照片：</span><br>' +
                        '<img src="/uploads/' + it.claimer_photo + '" style="max-width:140px;max-height:140px;border-radius:6px;margin-top:4px;border:1px solid #e2e8f0;">'
                      : '') +
                  '</div>'
                : "";
            var html =
                '<div class="detail-panel" style="margin:0;">' +
                '<div><span class="code" style="color:#666;font-size:13px;">编号 ' + it.code + '</span>' +
                '<span class="tag ' + (it.status === "已认领" ? "tag-returned" : "tag-pending") +
                '" style="margin-left:10px;">' + it.status + '</span></div>' +
                '<div style="font-size:18px;font-weight:600;margin:6px 0;">' + it.name + '</div>' +
                photoHtml +
                '<div class="detail-grid">' +
                '<div><span class="k">类别：</span><span class="v">' + (it.category || "—") + '</span></div>' +
                '<div><span class="k">捡到地点：</span><span class="v">' + (it.found_location || "—") + '</span></div>' +
                '<div><span class="k">捡到时间：</span><span class="v">' + (it.found_time || "—") + '</span></div>' +
                '<div><span class="k">捡到人：</span><span class="v">' + (it.founder || "—") + '</span></div>' +
                '<div><span class="k">登记时间：</span><span class="v">' + (it.created_at || "—") + '</span></div>' +
                '<div style="grid-column:1/-1;"><span class="k">特征描述：</span><br><span class="v">' +
                (it.description || "—") + '</span></div>' +
                '</div>' + claimHtml + '</div>';
            openModal(html);
        });
}

/* ===== 通用模态框 ===== */
function openModal(contentHtml) {
    var overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.style.cssText =
        "position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:9998;" +
        "display:flex;align-items:center;justify-content:center;padding:20px;";
    var box = document.createElement("div");
    box.style.cssText =
        "background:#fff;border-radius:10px;padding:24px;max-width:560px;" +
        "width:100%;max-height:85vh;overflow-y:auto;position:relative;";
    var close = document.createElement("span");
    close.textContent = "×";
    close.style.cssText =
        "position:absolute;top:8px;right:16px;font-size:26px;cursor:pointer;color:#999;";
    close.onclick = function () { overlay.remove(); };
    box.innerHTML = contentHtml;
    box.appendChild(close);
    box.onclick = function (e) { e.stopPropagation(); };
    overlay.onclick = function () { overlay.remove(); };
    overlay.appendChild(box);
    document.body.appendChild(overlay);
}

/* ===== 页面卸载时关摄像头 ===== */
window.addEventListener("beforeunload", stopCamera);
