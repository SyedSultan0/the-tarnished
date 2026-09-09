/* ============================================================
   THE TARNISHED — API client layer
   ----------------------------------------
   Talks to the existing THE TARNISHED FastAPI backend.

   Real endpoints used:
     GET  /health                          → connectivity + status
     GET  /audio/{file}                    → generated Telugu voice
     GET  /                                → root status
     POST /predict                         → image diagnosis + advisory
   ============================================================ */

"use strict";

/* Configurable API base URL.
   Override without editing code via a global:
     <script>window.TARNISHED_API_BASE_URL = "https://example.com";</script>
   Defaults to the local dev backend. */
var API_BASE_URL =
  (typeof window !== "undefined" && window.TARNISHED_API_BASE_URL) ||
  "http://localhost:8000";

/* Configurable WhatsApp destination (public chat link only — never a
   secret). Currently the Twilio WhatsApp Sandbox click-to-chat link
   (https://wa.me/14155238886).
   Override without editing code via a global:
      <script>window.TARNISHED_WHATSAPP_URL = "https://wa.me/14155238886";</script>
   When unset/empty the website hides the "Continue on WhatsApp" CTA
   so it never renders a broken link. */
var WHATSAPP_URL =
  (typeof window !== "undefined" && window.TARNISHED_WHATSAPP_URL) || "";

var REQUEST_TIMEOUT_MS = 60000; // 60s — model inference can be slow

/* User-facing error type. Never exposes raw stack traces. */
function ApiError(message, kind) {
  this.message = message;
  this.kind = kind || "api_error";
  this.name = "ApiError";
}
ApiError.prototype = Object.create(Error.prototype);
ApiError.prototype.constructor = ApiError;

/* Telangana districts understood by the backend, so the location
   selector and weather lookup stay consistent. */
var TELANGANA_DISTRICTS = [
  "Hyderabad", "Warangal", "Nizamabad", "Khammam", "Karimnagar",
  "Mahabubnagar", "Adilabad", "Nalgonda", "Sangareddy", "Medak",
  "Siddipet", "Jagtial", "Mancherial", "Peddapalli", "Kamareddy",
  "Bhongir", "Suryapet", "Jangaon", "Gadwal", "Nagarkurnool",
  "Vikarabad", "Yadadri"
];

var DISTRICT_COORDS = {
  hyderabad: [17.3850, 78.4867],
  warangal: [18.0000, 79.5833],
  nizamabad: [18.6713, 78.1019],
  khammam: [17.2473, 80.1514],
  karimnagar: [18.4392, 79.1286],
  mahabubnagar: [16.7422, 77.9856],
  adilabad: [19.6667, 78.5333],
  nalgonda: [17.0575, 79.2672],
  sangareddy: [17.6220, 78.1006],
  medak: [18.0417, 78.2640],
  siddipet: [18.1010, 78.8470],
  jagtial: [18.7954, 78.9167],
  mancherial: [18.8709, 79.4253],
  peddapalli: [18.6081, 79.3764],
  kamareddy: [18.3200, 78.3400],
  bhongir: [17.5150, 78.8900],
  suryapet: [17.1406, 79.6244],
  jangaon: [17.7247, 79.1680],
  gadwal: [16.2357, 77.7959],
  nagarkurnool: [16.4820, 78.3250],
  vikarabad: [17.3380, 77.9040],
  yadadri: [17.5885, 79.0280]
};

/* Simple fetch helper with a timeout and friendly error mapping. */
function request(method, url, opts) {
  opts = opts || {};
  var headers = opts.headers || {};
  var body = opts.body;
  var isForm = opts.isForm || false;

  if (!isForm && body && typeof body === "object" && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }

  var init = { method: method, headers: headers, body: body };

  return new Promise(function (resolve, reject) {
    var settled = false;
    var timer = setTimeout(function () {
      if (!settled) {
        settled = true;
        reject(new ApiError(
          "The service took too long to respond. Please try again.",
          "timeout"
        ));
      }
    }, REQUEST_TIMEOUT_MS);

    fetch(url, init)
      .then(function (res) {
        if (!settled) {
          settled = true;
          clearTimeout(timer);
          resolve(res);
        }
      })
      .catch(function () {
        if (!settled) {
          settled = true;
          clearTimeout(timer);
          reject(new ApiError(
            "Could not reach the analysis service. Make sure it is running.",
            "network"
          ));
        }
      });
  });
}

function join(base, path) {
  while (path.length > 0 && path[0] === "/") {
    path = path.substring(1);
  }
  return base.replace(/\/+$/, "") + "/" + path;
}

function readJson(res) {
  return res.text().then(function (text) {
    if (!text) {
      return {};
    }
    try {
      return JSON.parse(text);
    } catch (e) {
      throw new ApiError(
        "The service returned an unreadable response.",
        "unexpected"
      );
    }
  });
}

var TarnishedApi = {
  getBaseUrl: function () {
    return API_BASE_URL;
  },

  getDistricts: function () {
    return TELANGANA_DISTRICTS.slice();
  },

  getDistrictCoords: function (district) {
    if (!district) {
      return null;
    }
    var key = String(district).trim().toLowerCase();
    var coords = DISTRICT_COORDS[key];
    if (coords) {
      return { latitude: coords[0], longitude: coords[1] };
    }
    return null;
  },

  /* ---- Health check (real endpoint) ---- */
  checkHealth: function () {
    var url = join(API_BASE_URL, "/health");
    return request("GET", url).then(function (res) {
      return readJson(res).then(function (data) {
        return {
          ok: res.status === 200,
          data: data,
          message:
            res.status === 200
              ? null
              : "Service responded with an unexpected status."
        };
      });
    }).catch(function (err) {
      return { ok: false, data: {}, message: err.message };
    });
  },

  /* ---- Prediction (well-known path) ----
     Sends the image + form context to POST /predict (multipart/form-data). */
  predict: function (payload) {
    var url = join(API_BASE_URL, "/predict");
    var form = new FormData();
    form.append("image", payload.image, payload.filename || "crop.jpg");
    form.append("crop", payload.crop || "");
    if (payload.sowingDate) {
      form.append("sowing_date", payload.sowingDate);
    }
    if (payload.location) {
      form.append("location", payload.location);
    }
    if (payload.district) {
      form.append("district", payload.district);
    }
    if (payload.latitude != null) {
      form.append("latitude", String(payload.latitude));
    }
    if (payload.longitude != null) {
      form.append("longitude", String(payload.longitude));
    }

    return request("POST", url, { body: form, isForm: true }).then(function (res) {
      if (res.status === 404 || res.status === 405) {
        throw new ApiError(
          "The analysis service is not responding to this request. " +
          "Please try again in a moment.",
          "unexpected"
        );
      }
      if (res.status === 400 || res.status === 422) {
        return readJson(res).then(function (data) {
          var detail = data && (data.detail || data.message);
          throw new ApiError(
            "The analysis service rejected the request" +
              (detail ? ": " + detail : ".") +
              " Please check your input and try again.",
            "invalid_input"
          );
        });
      }
      if (res.status === 500 || res.status === 502 || res.status === 503) {
        throw new ApiError(
          "The analysis service ran into an error while processing your image. " +
          "Please try again.",
          "prediction_failed"
        );
      }
      if (res.status >= 200 && res.status < 300) {
        return readJson(res);
      }
      throw new ApiError(
        "The analysis service returned an unexpected response.",
        "unexpected"
      );
    });
  },

  /* Turn a possibly-relative audio URL into an absolute one. */
  resolveAudioUrl: function (url) {
    if (!url) {
      return null;
    }
    if (url.indexOf("http") === 0) {
      return url;
    }
    return join(API_BASE_URL, url);
  },

  /* Public WhatsApp chat destination for the website CTA, or "" when
     unconfigured (the UI then hides the CTA). Only http(s) links
     (e.g. https://wa.me/...) are accepted. */
  getWhatsAppUrl: function () {
    if (!WHATSAPP_URL) {
      return "";
    }
    var value = String(WHATSAPP_URL).trim();
    if (/^https?:\/\//i.test(value)) {
      return value;
    }
    return "";
  }
};

if (typeof module !== "undefined" && module.exports) {
  module.exports = { TarnishedApi: TarnishedApi, ApiError: ApiError };
}