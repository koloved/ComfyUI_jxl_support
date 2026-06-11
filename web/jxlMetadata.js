import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const L = console.log.bind(console, "[JXL]");
const W = console.warn.bind(console, "[JXL]");

// ── ISOBMFF JXL Container Parser ──────────────────────────────────────

function bytesToString(bytes) {
  return new TextDecoder("iso-8859-1").decode(bytes);
}

function parseBoxes(data) {
  var boxes = [];
  var offset = 0;
  var view = new DataView(data);
  while (offset + 8 <= data.byteLength) {
    var size = view.getUint32(offset);
    if (size === 0) break;
    if (size < 8 || offset + size > data.byteLength) break;
    var type = bytesToString(new Uint8Array(data, offset + 4, 4));
    boxes.push({ type: type, data: new Uint8Array(data, offset + 8, size - 8), size: size });
    offset += size;
  }
  return boxes;
}

function isJxlContainer(buffer) {
  if (buffer.byteLength < 32) return false;
  var u8 = new Uint8Array(buffer);
  return (
    u8[0] === 0x00 && u8[1] === 0x00 && u8[2] === 0x00 && u8[3] === 0x0c &&
    u8[4] === 0x4a && u8[5] === 0x58 && u8[6] === 0x4c && u8[7] === 0x20 &&
    u8[8] === 0x0d && u8[9] === 0x0a && u8[10] === 0x87 && u8[11] === 0x0a &&
    u8[12] === 0x00 && u8[13] === 0x00 && u8[14] === 0x00 && u8[15] === 0x14 &&
    u8[16] === 0x66 && u8[17] === 0x74 && u8[18] === 0x79 && u8[19] === 0x70 &&
    u8[20] === 0x6a && u8[21] === 0x78 && u8[22] === 0x6c && u8[23] === 0x20
  );
}

var _brotliFormats = [];
function detectBrotliFormat() {
  if (_brotliFormats.length > 0) return _brotliFormats;
  if (typeof DecompressionStream === "undefined") return [];
  var candidates = ["brotli", "br"];
  for (var i = 0; i < candidates.length; i++) {
    try { new DecompressionStream(candidates[i]); _brotliFormats.push(candidates[i]); } catch (e) {}
  }
  return _brotliFormats;
}

async function decompressBrotli(compressed) {
  var formats = detectBrotliFormat();
  if (formats.length === 0) {
    W("Brotli not supported in this browser");
    return null;
  }
  for (var f = 0; f < formats.length; f++) {
    try {
      var cs = new DecompressionStream(formats[f]);
      var blob = new Blob([compressed]);
      var stream = blob.stream().pipeThrough(cs);
      var reader = stream.getReader();
      var chunks = [];
      while (true) {
        var r = await reader.read();
        if (r.done) break;
        chunks.push(r.value);
      }
      var total = chunks.reduce(function (s, c) { return s + c.byteLength; }, 0);
      var result = new Uint8Array(total);
      var off = 0;
      for (var i = 0; i < chunks.length; i++) {
        result.set(chunks[i], off);
        off += chunks[i].byteLength;
      }
      L("Brotli decompressed:", total, "bytes", "format:", formats[f]);
      return result;
    } catch (e) {
      W('Brotli error with format "' + formats[f] + '":', e.message);
    }
  }
  return null;
}

async function getMetadataFromJxlBuffer(buffer) {
  if (!isJxlContainer(buffer)) { L("Not a valid JXL container"); return null; }
  var boxes = parseBoxes(buffer);
  for (var i = 0; i < boxes.length; i++) {
    if (boxes[i].type === "brob") {
      var innerType = bytesToString(boxes[i].data.subarray(0, 4));
      if (innerType !== "comf") continue;
      var compressed = boxes[i].data.subarray(4);
      var decompressed = await decompressBrotli(compressed);
      if (!decompressed) return null;
      try {
        var decoded = new TextDecoder("utf-8").decode(decompressed);
        return JSON.parse(decoded);
      } catch (e) {
        W("JSON parse error:", e.message);
        return null;
      }
    }
  }
  return null;
}

async function getMetadataFromJxlFile(file) {
  try {
    var buffer = await file.arrayBuffer();
    return await getMetadataFromJxlBuffer(buffer);
  } catch (e) { W("File read error:", e.message); return null; }
}

async function getMetadataFromServer(file) {
  try {
    var resp = await api.fetchApi("/jxl_metadata", {
      method: "POST",
      body: file,
      headers: { "Content-Type": "application/octet-stream" }
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch (e) { W("Server error:", e.message); return null; }
}

// ── Register Extension ─────────────────────────────────────────────────

app.registerExtension({
  name: "jxl_support",

  async setup() {
    L("Setting up JXL support extension");
    patchHandleFile();
  },
});

// ── Patch app.handleFile for drag-and-drop JXL workflow loading ───────

function patchHandleFile() {
  if (typeof app.handleFile !== "function") {
    W("app.handleFile not found, will retry on next drag");
    return;
  }
  if (app._jxlPatched) return;
  app._jxlPatched = true;
  L("Patching app.handleFile");

  var orig = app.handleFile.bind(app);
  app.handleFile = async function (file, source, opts) {
    if (file && file.name && file.name.toLowerCase().endsWith(".jxl")) {
      L("Intercepted .jxl file:", file.name);
      var meta = await getMetadataFromJxlFile(file);
      if (!meta) { L("Client-side failed, trying server..."); meta = await getMetadataFromServer(file); }
      if (meta) {
        var name = file.name.replace(/\.\w+$/, "");
        if (meta.workflow) {
          var wf = typeof meta.workflow === "string" ? JSON.parse(meta.workflow) : meta.workflow;
          if (wf && typeof wf === "object") {
            await app.loadGraphData(wf, true, true, name, {});
            L("Workflow loaded from JXL metadata");
            return;
          }
        }
        if (meta.prompt) {
          var p = typeof meta.prompt === "string" ? JSON.parse(meta.prompt) : meta.prompt;
          if (p && app.isApiJson(p)) {
            app.loadApiJson(p, name);
            L("Prompt loaded from JXL");
            return;
          }
        }
      }
      L("No metadata, falling through to default handler");
    }
    return orig(file, source, opts);
  };
  L("patchHandleFile success");
}

// ── Capture-phase drop interceptor (backup) ────────────────────────────

document.addEventListener("dragover", function (e) {
  try {
    var dt = e.dataTransfer;
    if (!dt || !dt.files) return;
    for (var i = 0; i < dt.files.length; i++) {
      if (dt.files[i].name && dt.files[i].name.toLowerCase().endsWith(".jxl")) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
    }
  } catch (ex) { /* ignore */ }
}, true);

document.addEventListener("drop", function (e) {
  try {
    var dt = e.dataTransfer;
    if (!dt || !dt.files) return;
    for (var i = 0; i < dt.files.length; i++) {
      var f = dt.files[i];
      if (f.name && f.name.toLowerCase().endsWith(".jxl")) {
        L("Drop interceptor caught .jxl file:", f.name);
        e.preventDefault();
        e.stopPropagation();
        (async function () {
          var meta = await getMetadataFromJxlFile(f);
          if (!meta) { meta = await getMetadataFromServer(f); }
          if (meta) {
            if (meta.workflow) {
              var wf = typeof meta.workflow === "string" ? JSON.parse(meta.workflow) : meta.workflow;
              if (wf && typeof wf === "object") {
                await app.loadGraphData(wf, true, true, f.name.replace(/\.\w+$/, ""), {});
                return;
              }
            }
            if (meta.prompt) {
              var p = typeof meta.prompt === "string" ? JSON.parse(meta.prompt) : meta.prompt;
              if (p && app.isApiJson(p)) { app.loadApiJson(p, f.name.replace(/\.\w+$/, "")); }
            }
          }
        })();
        return;
      }
    }
  } catch (ex) { W("Drop interceptor error:", ex.message); }
}, true);
