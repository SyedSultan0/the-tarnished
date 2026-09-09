/* ============================================================
   THE TARNISHED — frontend behavior
   ============================================================ */

"use strict";

/* ---------- Small helpers ---------- */
function get(id) {
  return document.getElementById(id);
}

function setHidden(id, hidden) {
  get(id).hidden = hidden;
}

function showError(container, message) {
  var el = get(container);
  el.textContent = message;
  el.hidden = false;
}

function clearError(container) {
  var el = get(container);
  el.textContent = "";
  el.hidden = true;
}

function escapeHtml(text) {
  if (text === null || text === undefined) {
    return "";
  }
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* The current trained model supports maize only. */
var SUPPORTED_CROP = "maize";
var CROP_NAMES = {
  maize: "Maize"
};

function todayISO() {
  var d = new Date();
  var y = d.getFullYear();
  var m = String(d.getMonth() + 1).padStart(2, "0");
  var day = String(d.getDate()).padStart(2, "0");
  return y + "-" + m + "-" + day;
}

/* ---------- DOM references ---------- */
var els = {
  form: get("analysis-form"),
  analyzeBtn: get("analyze-btn"),
  crop: get("crop"),
  sowingDate: get("sowing-date"),
  location: get("location"),
  districtList: get("district-list"),
  dropZone: get("drop-zone"),
  imageInput: get("image-input"),
  dzEmpty: get("dz-empty"),
  dzPreview: get("dz-preview"),
  previewImg: get("preview-img"),
  dzRemove: get("dz-remove"),
  imageError: get("image-error"),
  loading: get("loading"),
  formError: get("form-error"),
  results: get("results"),
  statusPill: get("server-status"),

  resultDiagnosis: get("result-diagnosis"),
  resultCrop: get("result-crop"),
  resultWeather: get("result-weather"),
  resultRecommended: get("result-recommended"),
  resultTelugu: get("result-telugu"),
  voiceBlock: get("voice-block"),
  whatsappCta: get("whatsapp-cta"),
  whatsappLink: get("whatsapp-link"),
  voicePlay: get("voice-play"),
  voiceLabel: get("voice-label"),
  voiceAudio: get("voice-audio"),
  voiceHint: get("voice-hint")
};

/* Current selected image file. */
var state = {
  image: null,
  audioUrl: null
};

/* ---------- Init ---------- */
function initDistricts() {
  els.districtList.innerHTML = "";
  TarnishedApi.getDistricts().forEach(function (d) {
    var opt = document.createElement("option");
    opt.value = d;
    els.districtList.appendChild(opt);
  });
}

function initDateLimits() {
  els.sowingDate.max = todayISO();
}

/* ---------- WhatsApp CTA ----------
   Shown only when a public WhatsApp destination is configured via
   window.TARNISHED_WHATSAPP_URL (see js/api.js). Otherwise the CTA
   stays hidden so there is never a broken link. */
function initWhatsAppCta() {
  if (!els.whatsappCta || !els.whatsappLink) {
    return;
  }
  var url = "";
  try {
    url = TarnishedApi.getWhatsAppUrl();
  } catch (err) {
    url = "";
  }
  if (!url) {
    els.whatsappCta.hidden = true;
    return;
  }
  els.whatsappLink.href = url;
  els.whatsappCta.hidden = false;
}

/* ---------- Server status pill ---------- */
function updateStatusPill(status, label) {
  els.statusPill.setAttribute("data-state", status);
  elStatusText().textContent = label;
}

function elStatusText() {
  var pills = els.statusPill.querySelectorAll(".status-text");
  return pills[0];
}

function checkServerStatus() {
  updateStatusPill("checking", "Checking service…");
  TarnishedApi.checkHealth().then(function (result) {
    if (result.ok) {
      updateStatusPill("online", "Service online");
    } else {
      updateStatusPill(
        "offline",
        "Cannot reach the service. Starting analysis will fail."
      );
    }
  });
}

/* Entry point */
(function init() {
  initDistricts();
  initDateLimits();
  initWhatsAppCta();
  checkServerStatus();
})();

/* ============================================================
   IMAGE UPLOAD (click + drag & drop + preview + remove)
   ============================================================ */

var MAX_IMAGE_BYTES = 5 * 1024 * 1024; // 5 MB

function validImageType(file) {
  return file && file.type && file.type.indexOf("image/") === 0;
}

function setImageError(message) {
  if (!message) {
    els.imageError.hidden = true;
    return;
  }
  els.imageError.textContent = message;
  els.imageError.hidden = false;
}

function acceptFile(file) {
  setImageError(null);
  if (!file) {
    return;
  }
  if (!validImageType(file)) {
    setImageError("That file is not an image. Please upload a JPG, PNG or WEBP photo.");
    return;
  }
  if (file.size > MAX_IMAGE_BYTES) {
    setImageError("The image is larger than 5 MB. Please choose a smaller photo.");
    return;
  }

  var reader = new FileReader();
  reader.onload = function () {
    state.image = file;
    els.previewImg.src = reader.result;
    els.dzEmpty.hidden = true;
    els.dzPreview.hidden = false;
    els.dzRemove.hidden = false;
  };
  reader.onerror = function () {
    setImageError("Could not read that image. Please try a different photo.");
  };
  reader.readAsDataURL(file);
}

function clearImage() {
  state.image = null;
  els.imageInput.value = "";
  els.previewImg.removeAttribute("src");
  els.dzPreview.hidden = true;
  els.dzEmpty.hidden = false;
  els.dzRemove.hidden = true;
  setImageError(null);
}

function bindImageUpload() {
  // Click to upload
  els.dropZone.addEventListener("click", function () {
    els.imageInput.click();
  });

  els.imageInput.addEventListener("change", function () {
    if (els.imageInput.files && els.imageInput.files.length > 0) {
      acceptFile(els.imageInput.files[0]);
    }
  });

  // Remove button
  els.dzRemove.addEventListener("click", function (evt) {
    evt.stopPropagation();
    clearImage();
  });

  // Keyboard access (Enter / Space)
  els.dropZone.addEventListener("keydown", function (evt) {
    if (evt.key === "Enter" || evt.key === " ") {
      evt.preventDefault();
      els.imageInput.click();
    }
  });

  // Drag & drop
  els.dropZone.addEventListener("dragover", function (evt) {
    evt.preventDefault();
    evt.dataTransfer.dropEffect = "copy";
    els.dropZone.classList.add("dragover");
  });
  els.dropZone.addEventListener("dragleave", function () {
    els.dropZone.classList.remove("dragover");
  });
  els.dropZone.addEventListener("drop", function (evt) {
    evt.preventDefault();
    els.dropZone.classList.remove("dragover");
    if (evt.dataTransfer.files && evt.dataTransfer.files.length > 0) {
      acceptFile(evt.dataTransfer.files[0]);
    }
  });
}

/* ============================================================
   VALIDATION & SUBMIT
   ============================================================ */

function validateForm() {
  clearError("form-error");
  clearError("image-error");

  if (!els.sowingDate.value) {
    showError("form-error", "Please choose the sowing date.");
    return null;
  }
  if (els.sowingDate.value > els.sowingDate.max) {
    showError(
      "form-error",
      "The sowing date cannot be in the future. Please choose a valid date."
    );
    return null;
  }
  if (!state.image) {
    setImageError("Please upload a photo of your crop before analyzing.");
    return null;
  }

  var district = els.location.value.trim();
  var coords = district ? TarnishedApi.getDistrictCoords(district) : null;

  // The current model supports maize only, so the crop is fixed.
  return {
    crop: SUPPORTED_CROP,
    sowingDate: els.sowingDate.value,
    location: district || null,
    district: district || null,
    latitude: coords ? coords.latitude : null,
    longitude: coords ? coords.longitude : null,
    image: state.image,
    filename: state.image.name
  };
}

function setLoading(on) {
  els.loading.hidden = !on;
  els.analyzeBtn.disabled = on;
  els.analyzeBtn.textContent = on ? "Analyzing…" : "Analyze Crop";
  if (on) {
    els.results.hidden = true;
  }
}

function handlePredictError(err) {
  els.loading.hidden = true;
  els.analyzeBtn.disabled = false;
  els.analyzeBtn.textContent = "Analyze Crop";
  showError("form-error", err.message || "Something went wrong. Please try again.");
}

function submitAnalysis() {
  var payload = validateForm();
  if (!payload) {
    return;
  }

  setLoading(true);

  TarnishedApi.predict(payload)
    .then(renderResults)
    .catch(handlePredictError);
}

function bindEvents() {
  els.form.addEventListener("submit", function (evt) {
    evt.preventDefault();
    submitAnalysis();
  });

  bindImageUpload();
}

/* ============================================================
   RESULT RENDERING
   ============================================================ */

/* Normalize a result into the sections the UI understands. */
function normalizeResult(data) {
  data = data || {};
  var diagnosis = data.diagnosis || {};
  var cropInfo = data.crop_info || data.cropInfo || {};
  var weather = data.weather || {};
  var advisory = data.advisory || {};

  if (!diagnosis.disease && data.disease) {
    diagnosis = {
      disease: data.disease,
      disease_display: data.disease_display || data.disease_name,
      confidence: data.confidence,
      status: data.status
    };
  }
  if (!cropInfo.stage_name && data.crop_stage) {
    cropInfo = {
      crop: data.crop,
      stage_name: data.crop_stage,
      stage_description: data.stage_description,
      days_since_sowing: data.days_since_sowing,
      days_until_harvest: data.days_until_harvest,
      progress_percentage: data.progress_percentage,
      is_critical: data.is_critical
    };
  }
  if (!weather.risk_level && data.weather_risk_level) {
    weather = {
      risk_level: data.weather_risk_level,
      risk_score: data.weather_risk_score,
      summary: data.weather_summary,
      risk_factors: data.risk_factors
    };
  }

  return {
    diagnosis: diagnosis,
    cropInfo: cropInfo,
    weather: weather,
    advisory: advisory,
    teluguAdvisory: data.telugu_advisory || data.teluguAdvisory || data.advisory_te,
    audioUrl: data.audio_url || data.audioUrl
  };
}

function renderResults(data) {
  var r = normalizeResult(data);

  els.loading.hidden = true;
  els.analyzeBtn.disabled = false;
  els.analyzeBtn.textContent = "Analyze Crop";
  clearError("form-error");

  renderDiagnosis(r.diagnosis);
  renderCrop(r.cropInfo);
  renderWeather(r.weather);
  renderRecommended(r.advisory);
  renderTelugu(r.teluguAdvisory);
  renderVoice(r.audioUrl);

  els.results.hidden = false;
  if (els.results.focus) {
    els.results.focus();
  }
}

function renderDiagnosis(diag) {
  var disease =
    diag.disease_display ||
    diag.disease_name ||
    diag.disease ||
    "Not identified";
  var rawConf = diag.confidence;
  var confPercent = null;
  if (typeof rawConf === "number") {
    confPercent = rawConf > 1 ? rawConf : rawConf * 100;
  }

  var status = String(diag.status || "");
  var badge = "";
  var note = "";
  if (status === "high_confidence") {
    badge = '<span class="badge ok">High confidence</span>';
  } else if (status === "uncertain" || (confPercent !== null && confPercent < 70)) {
    badge = '<span class="badge warn">Low confidence — verify with an expert</span>';
    note =
      "<p class=\"diagnosis-note\">The model is not fully confident in this " +
      "result. Please confirm the symptoms with a local agricultural officer.</p>";
  }

  var confRow = "";
  if (confPercent !== null) {
    var shown = Math.round(confPercent * 10) / 10;
    confRow =
      '<div class="confidence-row">' +
      '<span class="confidence-value">' + escapeHtml(String(shown)) + "% confidence</span>" +
      '<span class="confidence-bar-track"><span class="confidence-bar" ' +
      'style="width:' + Math.max(0, Math.min(100, confPercent)) + '%"></span></span>' +
      badge +
      "</div>";
  } else {
    confRow = badge ? '<div class="confidence-row">' + badge + "</div>" : "";
  }

  els.resultDiagnosis.innerHTML =
    '<div class="diagnosis-card">' +
    '<p class="diagnosis-name">' + escapeHtml(disease) + "</p>" +
    confRow +
    note +
    "</div>";
}

function renderCrop(crop) {
  var rows = "";
  var add = function (label, value) {
    if (value === null || value === undefined || value === "") {
      return;
    }
    rows += "<dt>" + escapeHtml(label) + "</dt><dd>" + escapeHtml(String(value)) + "</dd>";
  };

  add("Crop", crop.crop ? (CROP_NAMES[crop.crop] || crop.crop) : null);

  var stageName = crop.stage_name || crop.stage;
  add("Crop stage", stageName);

  var whenInfo = [];
  if (crop.days_since_sowing !== null && crop.days_since_sowing !== undefined) {
    whenInfo.push(crop.days_since_sowing + " days since sowing");
  }
  if (crop.days_until_harvest !== null && crop.days_until_harvest !== undefined) {
    whenInfo.push("~" + crop.days_until_harvest + " days to harvest");
  }
  if (crop.progress_percentage !== null && crop.progress_percentage !== undefined) {
    whenInfo.push(
      Math.round(Number(crop.progress_percentage) * 10) / 10 + "% progress"
    );
  }
  if (crop.is_critical) {
    whenInfo.push("critical stage");
  }

  var extra = "";
  if (crop.stage_description) {
    extra =
      '<dd class="detail-when">' + escapeHtml(String(crop.stage_description)) + "</dd>";
  } else if (whenInfo.length > 0) {
    extra = '<dd class="detail-when">' + escapeHtml(whenInfo.join(" · ")) + "</dd>";
  }

  if (rows === "" && extra === "") {
    els.resultCrop.innerHTML = '<p class="field-hint">No crop information returned.</p>';
    return;
  }

  els.resultCrop.innerHTML = rows + extra;
}

function renderWeather(weather) {
  var level = String(weather.risk_level || "").toLowerCase();
  if (!level) {
    els.resultWeather.innerHTML =
      '<p class="field-hint">No weather information returned.</p>';
    return;
  }

  // The backend may report either "medium" or "moderate".
  var risk = level;
  var label;
  if (level === "high") {
    label = "High risk";
  } else if (level === "medium" || level === "moderate") {
    risk = "medium";
    label = "Medium risk";
  } else {
    label = "Low risk";
  }

  var summary = weather.summary
    ? '<p class="weather-summary">' + escapeHtml(String(weather.summary)) + "</p>"
    : "";

  els.resultWeather.innerHTML =
    '<span class="weather-pill" data-risk="' + escapeHtml(risk) + '">' +
    '<span class="pill-dot" aria-hidden="true"></span>' +
    escapeHtml(label) +
    "</span>" +
    summary;
}

function renderRecommended(advisory) {
  if (!advisory || typeof advisory !== "object") {
    els.resultRecommended.innerHTML =
      '<p class="field-hint">No recommended action returned.</p>';
    return;
  }
  els.resultRecommended.innerHTML = buildRecommendedRows(advisory);
}

function buildRecommendedRows(advisory) {
  var rows = "";
  var addRow = function (label, value) {
    if (value === null || value === undefined || String(value).trim() === "") {
      return;
    }
    rows +=
      '<div class="rec-row"><span class="rec-label">' + escapeHtml(label) + "</span>" +
      '<span class="rec-value">' + escapeHtml(String(value)) + "</span></div>";
  };

  addRow("Action", advisory.action);
  addRow("Product", advisory.product);
  addRow("Dosage", advisory.dosage);
  addRow("Timing", advisory.timing);
  addRow("Method", advisory.method);
  addRow("Expected result", advisory.expected_result);

  if (advisory.stage_susceptibility) {
    addRow("Stage risk", advisory.stage_susceptibility);
  }

  var safety = advisory.safety_precautions;
  if (safety && safety.length > 0) {
    var items = "";
    safety.forEach(function (s) {
      items += "<li>" + escapeHtml(String(s)) + "</li>";
    });
    rows +=
      '<div class="rec-row rec-safety"><strong>Safety precautions</strong>' +
      "<ul>" + items + "</ul></div>";
  }

  if (advisory.urgency) {
    var tag = String(advisory.urgency).toLowerCase();
    var cls = /immediate|urgent/.test(tag)
      ? "immediate"
      : /soon/.test(tag) ? "soon" : "plan";
    rows +=
      '<div class="rec-row rec-urgency"><strong>Urgency</strong>' +
      '<span class="urgency-tag ' + cls + '">' +
      escapeHtml(String(advisory.urgency)) + "</span></div>";
  }

  if (rows === "") {
    return '<p class="field-hint">No recommended action returned.</p>';
  }
  return '<div class="rec-rows">' + rows + "</div>";
}

function renderTelugu(text) {
  if (!text) {
    els.resultTelugu.innerHTML =
      '<p class="field-hint">No Telugu advisory returned.</p>';
    return;
  }
  els.resultTelugu.innerHTML = escapeHtml(String(text));
}

function renderVoice(audioUrl) {
  var url = TarnishedApi.resolveAudioUrl(audioUrl);
  if (!url) {
    els.voiceBlock.hidden = true;
    return;
  }
  state.audioUrl = url;
  els.voiceBlock.hidden = false;
  els.voiceHint.textContent =
    "A Telugu voice recording is available from the service.";
  setupVoicePlayer();
}

/* Voice playback (uses the real /audio URL from the backend). */
var voiceBound = false;
var voicePlaying = false;

function setVoicePlaying(on) {
  voicePlaying = on;
  els.voiceLabel.textContent = on ? "Pause Telugu Advisory" : "Play Telugu Advisory";
  if (on) {
    els.voicePlay.classList.add("playing");
  } else {
    els.voicePlay.classList.remove("playing");
  }
}

function setupVoicePlayer() {
  if (voiceBound) {
    return;
  }
  voiceBound = true;

  els.voicePlay.addEventListener("click", function () {
    var audio = els.voiceAudio;
    if (!state.audioUrl) {
      return;
    }
    if (voicePlaying) {
      audio.pause();
      return;
    }
    audio.src = state.audioUrl;
    audio.play().catch(function () {
      setVoicePlaying(false);
      els.voiceHint.textContent =
        "The voice recording could not be played. Please view the Telugu text above.";
    });
  });

  els.voiceAudio.addEventListener("play", function () {
    setVoicePlaying(true);
  });
  els.voiceAudio.addEventListener("pause", function () {
    setVoicePlaying(false);
  });
  els.voiceAudio.addEventListener("ended", function () {
    setVoicePlaying(false);
  });
  els.voiceAudio.addEventListener("error", function () {
    setVoicePlaying(false);
    els.voiceHint.textContent =
      "The voice recording could not be played. Please view the Telugu text above.";
  });
}

/* Start event wiring once the DOM is ready. */
bindEvents();