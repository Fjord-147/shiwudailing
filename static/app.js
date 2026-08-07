/* 和康中医医院失物招领系统 - 公共脚本 */

/* ===== 全局照片放大查看器（所有页面共享，支持多图+缩放+关闭）===== */
var GZOOM = {idx:0, photos:[], scale:1};
function gZoomOpen(photos, startIdx){
    if(!photos || photos.length===0) return;
    gZoomClose();
    GZOOM.photos = photos; GZOOM.idx = startIdx || 0; GZOOM.scale = 1;
    var overlay = document.createElement('div');
    overlay.className = 'photo-zoom-overlay';
    overlay.id = 'gZoomOverlay';
    overlay.innerHTML =
        '<div class="photo-zoom-bar">'+
            '<button data-act="out" title="缩小">➖</button>'+
            '<span id="gZoomLabel">100%</span>'+
            '<button data-act="in" title="放大">➕</button>'+
            '<button data-act="reset" title="还原">⟲</button>'+
            '<span id="gZoomCount"></span>'+
            '<button data-act="prev" title="上一张">‹</button>'+
            '<button data-act="next" title="下一张">›</button>'+
            '<button data-act="close" class="close-zoom" title="关闭">✕ 关闭</button>'+
        '</div>'+
        '<div class="photo-zoom-stage"><img id="gZoomImg"></div>';
    document.body.appendChild(overlay);
    overlay.querySelector('.photo-zoom-bar').addEventListener('click', function(e){
        var btn = e.target.closest('button'); if(!btn) return;
        var act = btn.getAttribute('data-act');
        if(act==='out') gZoomScale(-0.2);
        else if(act==='in') gZoomScale(0.2);
        else if(act==='reset'){ GZOOM.scale=1; gZoomApply(); }
        else if(act==='prev') gZoomStep(-1);
        else if(act==='next') gZoomStep(1);
        else if(act==='close') gZoomClose();
    });
    overlay.addEventListener('click', function(e){ if(e.target===overlay) gZoomClose(); });
    document.getElementById('gZoomImg').addEventListener('wheel', function(e){
        e.preventDefault(); gZoomScale(e.deltaY<0 ? 0.15 : -0.15);
    });
    gZoomShow();
}
function gZoomShow(){
    var img = document.getElementById('gZoomImg');
    if(img) img.src = '/uploads/'+GZOOM.photos[GZOOM.idx];
    var c = document.getElementById('gZoomCount');
    if(c) c.textContent = GZOOM.photos.length>1 ? ((GZOOM.idx+1)+'/'+GZOOM.photos.length) : '';
    GZOOM.scale = 1; gZoomApply();
}
function gZoomStep(dir){
    if(GZOOM.photos.length<=1) return;
    GZOOM.idx = (GZOOM.idx + dir + GZOOM.photos.length) % GZOOM.photos.length;
    gZoomShow();
}
function gZoomScale(delta){
    GZOOM.scale = Math.max(0.2, Math.min(5, GZOOM.scale + delta));
    gZoomApply();
}
function gZoomApply(){
    var img = document.getElementById('gZoomImg');
    if(img) img.style.transform = 'scale('+GZOOM.scale+')';
    var lb = document.getElementById('gZoomLabel');
    if(lb) lb.textContent = Math.round(GZOOM.scale*100)+'%';
}
function gZoomClose(){
    var o = document.getElementById('gZoomOverlay'); if(o) o.remove();
}
document.addEventListener('keydown', function(e){
    if(document.getElementById('gZoomOverlay')){
        if(e.key==='Escape') gZoomClose();
        else if(e.key==='ArrowLeft') gZoomStep(-1);
        else if(e.key==='ArrowRight') gZoomStep(1);
    }
});
/* 便捷封装：传入逗号分隔的photo字段，点击放大 */
function gZoomFromField(photoField, idx){
    var photos = (photoField||'').split(',').map(function(s){return s.trim();}).filter(Boolean);
    gZoomOpen(photos, idx||0);
}
/* 从图片元素点击放大：照片列表存在父容器的 data-p（base64），点的是第 data-idx 张 */
function gZoomFromImg(img){
    try{
        var box = img.closest('[data-p]');
        var photos = JSON.parse(decodeURIComponent(escape(atob(box.getAttribute('data-p')))));
        gZoomOpen(photos, parseInt(img.getAttribute('data-idx'))||0);
    }catch(e){}
}

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
            // 照片：解析逗号分隔的多张，横向排列
            var photos = it.photo ? it.photo.split(',').map(function(s){return s.trim();}).filter(Boolean) : [];
            var photoHtml;
            if (photos.length > 0) {
                var pAttr = btoa(unescape(encodeURIComponent(JSON.stringify(photos))));
                photoHtml = '<div class="detail-photos" data-p="' + pAttr + '">' + photos.map(function(p, i){
                    return '<img class="photo-big" src="/uploads/' + p + '" data-idx="' + i + '" onclick="gZoomFromImg(this)">';
                }).join('') + '</div>';
            } else {
                photoHtml = '<div style="color:#999;margin:10px 0;">（无照片）</div>';
            }
            var claimHtml = it.status === "已认领"
                ? '<div style="margin-top:14px;padding-top:12px;border-top:1px dashed #ccc;">' +
                  '<strong>认领信息</strong><br>' +
                  '认领人：' + (it.claimer_name || "") + '　' +
                  '电话：' + (it.claimer_phone || "未留") + '<br>' +
                  '人群：' + (it.claimer_group || "未选") + '　' +
                  '性别：' + (it.claimer_gender || "未选") + '<br>' +
                  '认领时间：' + (it.claimed_at || "") + '　' +
                  '经办人：' + (it.operator || "") + '<br>' +
                  '特征已核实：' + (it.feature_verified ? "是" : "否") +
                  (it.claimer_photo
                      ? '<br><span class="k">认领人照片：</span><br>' +
                        '<img src="/uploads/' + it.claimer_photo + '" style="max-width:140px;max-height:140px;border-radius:6px;margin-top:4px;border:1px solid #e2e8f0;cursor:zoom-in;" onclick="gZoomOpen([\'' + it.claimer_photo + '\'],0)">'
                      : '') +
                  '<div class="claim-actions">' +
                    '<button class="btn btn-sm btn-danger-outline" onclick="doUnclaim(' + it.id + ',\'' + escapeHtml(it.code) + '\')">↩ 撤销认领</button>' +
                    '<button class="btn btn-sm btn-secondary" onclick="doEditClaim(' + JSON.stringify(it).replace(/'/g,"&#39;") + ')">✎ 修改信息</button>' +
                    '<button class="btn btn-sm btn-danger-outline" onclick="doDelete(' + it.id + ',\'' + escapeHtml(it.code) + '\',\'' + escapeHtml(it.name) + '\')">🗑 删除记录</button>' +
                  '</div>' +
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
                '<div><span class="k">存放位置：</span><span class="v">' + (it.storage_location || "—") + '</span></div>' +
                '<div><span class="k">捡到时间：</span><span class="v">' + (it.found_time || "—") + '</span></div>' +
                '<div><span class="k">捡到人：</span><span class="v">' + (it.founder || "—") + '</span></div>' +
                '<div><span class="k">登记时间：</span><span class="v">' + (it.created_at || "—") + '</span></div>' +
                '<div style="grid-column:1/-1;"><span class="k">特征描述：</span><br><span class="v">' +
                (it.description || "—") + '</span></div>' +
                '</div>' + claimHtml +
                (it.status === "待认领"
                    ? '<div class="claim-actions" style="margin-top:14px;padding-top:12px;border-top:1px dashed #ccc;">' +
                      '<button class="btn btn-sm btn-danger-outline" onclick="doDelete(' + it.id + ',\'' + escapeHtml(it.code) + '\',\'' + escapeHtml(it.name) + '\')">🗑 删除记录</button>' +
                      '</div>'
                    : '') +
                '</div>';
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

/* ===== 危险操作确认弹窗（必须输入“确认”二字）===== */
function confirmDanger(title, hint, onConfirm){
    var html =
        '<div style="text-align:center;">' +
        '<div style="font-size:40px;margin-bottom:8px;">⚠️</div>' +
        '<div style="font-size:18px;font-weight:600;margin-bottom:8px;">' + escapeHtml(title) + '</div>' +
        '<div style="color:#6b7280;font-size:14px;margin-bottom:16px;">' + escapeHtml(hint) + '</div>' +
        '<div style="background:#fff3e0;border:1px solid #ffe0b2;border-radius:6px;padding:10px;margin-bottom:14px;font-size:13px;color:#e65100;">' +
        '请在下方输入框输入 <strong>确认</strong> 二字才会执行</div>' +
        '<input type="text" id="dangerConfirmInput" class="form-control" placeholder="输入 确认" ' +
        'oninput="var b=document.getElementById(\'dangerConfirmBtn\'); b.disabled = (this.value.trim()!==\'确认\');" style="text-align:center;font-size:16px;margin-bottom:16px;">' +
        '<div style="display:flex;gap:10px;">' +
        '<button class="btn btn-secondary" style="flex:1;" onclick="this.closest(\'.modal-overlay\').remove()">取消</button>' +
        '<button class="btn btn-danger" id="dangerConfirmBtn" style="flex:1;" disabled>确定执行</button>' +
        '</div></div>';
    openModal(html);
    document.getElementById('dangerConfirmBtn').onclick = function(){
        this.closest('.modal-overlay').remove();
        if(onConfirm) onConfirm();
    };
}

/* ===== 认领管理操作（撤销/删除/修改）===== */
function doUnclaim(itemId, code){
    confirmDanger('撤销认领', '物品 ' + code + ' 将退回「待认领」，认领人信息会被清空。', function(){
        fetch('/api/item/'+itemId+'/unclaim', {
            method:'POST',
            headers:{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'fetch'},
            body:'confirm=' + encodeURIComponent('确认')
        }).then(function(r){return r.json();})
          .then(function(d){
              toast(d.msg, d.ok ? 'success' : 'error');
              if(d.ok){
                  var ov = document.querySelector('.modal-overlay'); if(ov) ov.remove();
                  setTimeout(function(){ location.reload(); }, 800);
              }
          });
    });
}

function doDelete(itemId, code, name){
    confirmDanger('删除整条记录', '将永久删除 ' + code + ' ' + name + ' 及其所有照片，无法恢复！', function(){
        fetch('/api/item/'+itemId+'/delete', {
            method:'POST',
            headers:{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'fetch'},
            body:'confirm=' + encodeURIComponent('确认')
        }).then(function(r){return r.json();})
          .then(function(d){
              toast(d.msg, d.ok ? 'success' : 'error');
              if(d.ok){
                  var ov = document.querySelector('.modal-overlay'); if(ov) ov.remove();
                  setTimeout(function(){ location.reload(); }, 800);
              }
          });
    });
}

function doEditClaim(it){
    var html =
        '<form onsubmit="event.preventDefault();submitEditClaim('+it.id+');">' +
        '<div style="font-size:18px;font-weight:600;margin-bottom:16px;">修改认领信息 <span style="color:#6b7280;font-size:14px;font-weight:normal;">'+escapeHtml(it.code)+'</span></div>' +
        '<div class="form-group" style="margin-bottom:14px;"><label>认领人姓名 <span class="req">*</span></label><input type="text" id="ec_name" class="form-control" value="'+escapeHtml(it.claimer_name||'')+'" required></div>' +
        '<div class="form-group" style="margin-bottom:14px;"><label>认领人电话</label><input type="text" id="ec_phone" class="form-control" value="'+escapeHtml(it.claimer_phone||'')+'"></div>' +
        '<div class="form-group" style="margin-bottom:14px;"><label>人群</label><select id="ec_group" class="form-control">'+
            ['老人','小孩','青年','中年','其他'].map(function(g){return '<option value="'+g+'"'+(it.claimer_group===g?' selected':'')+'>'+g+'</option>';}).join('')+
            '</select></div>' +
        '<div class="form-group" style="margin-bottom:18px;"><label>性别</label><select id="ec_gender" class="form-control">'+
            '<option value="">请选择</option><option value="男"'+(it.claimer_gender==='男'?' selected':'')+'>男士</option><option value="女"'+(it.claimer_gender==='女'?' selected':'')+'>女士</option>'+
            '</select></div>' +
        '<div style="display:flex;gap:10px;"><button type="button" class="btn btn-secondary" style="flex:1;" onclick="this.closest(\'.modal-overlay\').remove()">取消</button>' +
        '<button type="submit" class="btn" style="flex:1;">保存修改</button></div>' +
        '</form>';
    openModal(html);
}
/* 卡片用：先取详情再弹修改表单 */
function editClaimById(itemId){
    fetch('/api/item/'+itemId).then(function(r){return r.json();})
        .then(function(d){ if(d.ok) doEditClaim(d.item); else toast('读取失败','error'); });
}

function submitEditClaim(itemId){
    var fd = new URLSearchParams();
    fd.append('claimer_name', document.getElementById('ec_name').value.trim());
    fd.append('claimer_phone', document.getElementById('ec_phone').value.trim());
    fd.append('claimer_group', document.getElementById('ec_group').value);
    fd.append('claimer_gender', document.getElementById('ec_gender').value);
    fetch('/api/item/'+itemId+'/edit-claim', {
        method:'POST',
        headers:{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'fetch'},
        body:fd.toString()
    }).then(function(r){return r.json();})
      .then(function(d){
          toast(d.msg, d.ok ? 'success' : 'error');
          if(d.ok){
              var ov = document.querySelector('.modal-overlay'); if(ov) ov.remove();
              setTimeout(function(){ location.reload(); }, 800);
          }
      });
}

/* ===== 页面卸载时关摄像头 ===== */
window.addEventListener("beforeunload", stopCamera);
