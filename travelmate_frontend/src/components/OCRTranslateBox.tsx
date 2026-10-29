import { useState, useRef, useEffect, useMemo } from "react";
import { extractOCRText, translateText } from "@/lib/api";
import { LanguageSelector, getStoredLanguage } from "@/components/LanguageSelector";
import {
  Camera,
  Languages,
  RefreshCcw,
  AlertCircle,
  CheckCircle2,
  Loader2,
  X,
  FileImage,
  Copy,
  Upload,
  SwitchCamera,
  RotateCcw,
  Utensils,
  FileText,
  Sparkles,
} from "lucide-react";

const MAX_SIZE_MB = 10;
const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp", "image/bmp"];

type LoadState = "idle" | "loading" | "done" | "error";

interface ParsedMenuItem {
  originalName: string;
  translatedName?: string;
  price: string;
}

function parseMenuItems(ocr: string | null, trans: string | null): ParsedMenuItem[] {
  if (!ocr) return [];

  const priceRegex = /(?:Rs\.?|₹|\$|€)\s*([0-9]+(?:[.,][0-9]{1,2})?)|([0-9]+(?:[.,][0-9]{1,2})?)\s*(?:Rs\.?|₹|\$|€)/i;
  const ocrLines = ocr.split("\n").map((l) => l.trim()).filter(Boolean);
  const transLines = trans ? trans.split("\n").map((l) => l.trim()).filter(Boolean) : [];

  const items: ParsedMenuItem[] = [];

  for (let i = 0; i < ocrLines.length; i++) {
    const line = ocrLines[i];
    const match = line.match(priceRegex);
    if (match) {
      const priceStr = match[0].trim();
      let cleanOrig = line
        .replace(match[0], "")
        .replace(/[\.·\-–—]{2,}/g, " ")
        .trim();

      let cleanTrans = "";
      if (transLines[i]) {
        cleanTrans = transLines[i]
          .replace(priceRegex, "")
          .replace(/[\.·\-–—]{2,}/g, " ")
          .trim();
      }

      if (cleanOrig.length > 0) {
        items.push({
          originalName: cleanOrig,
          translatedName: cleanTrans || undefined,
          price: priceStr,
        });
      }
    }
  }

  return items;
}

function StatusBadge({ state, label }: { state: LoadState; label: string }) {
  if (state === "loading")
    return (
      <span className="inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400">
        <Loader2 className="h-3 w-3 animate-spin" /> {label}
      </span>
    );
  if (state === "done")
    return (
      <span className="inline-flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
        <CheckCircle2 className="h-3 w-3" /> Done
      </span>
    );
  if (state === "error")
    return (
      <span className="inline-flex items-center gap-1 text-xs text-red-500">
        <AlertCircle className="h-3 w-3" /> Failed
      </span>
    );
  return null;
}

export const OCRTranslateBox = () => {
  const [ocrLang, setOcrLang] = useState<string>("kan+eng");
  const [targetLang, setTargetLang] = useState(getStoredLanguage());
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);

  const [isCameraActive, setIsCameraActive] = useState<boolean>(false);
  const [facingMode, setFacingMode] = useState<"environment" | "user">("environment");
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [isStartingCamera, setIsStartingCamera] = useState<boolean>(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const [ocrState, setOcrState] = useState<LoadState>("idle");
  const [ocrText, setOcrText] = useState<string | null>(null);
  const [ocrError, setOcrError] = useState<string | null>(null);
  const [ocrEngine, setOcrEngine] = useState<string | null>(null);

  const [transState, setTransState] = useState<LoadState>("idle");
  const [translatedText, setTranslatedText] = useState<string | null>(null);
  const [transError, setTransError] = useState<string | null>(null);
  const [transProvider, setTransProvider] = useState<string | null>(null);

  const [copied, setCopied] = useState<"ocr" | "trans" | null>(null);
  const [viewMode, setViewMode] = useState<"menu" | "raw">("menu");

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsCameraActive(false);
    setIsStartingCamera(false);
  };

  const startCamera = async (facing: "environment" | "user" = facingMode) => {
    setCameraError(null);
    setIsStartingCamera(true);

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setCameraError(
        "Camera API is not supported on this device/browser. Please upload an image instead."
      );
      setIsStartingCamera(false);
      return;
    }

    try {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: facing },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      });

      streamRef.current = stream;
      setIsCameraActive(true);
      setFacingMode(facing);

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => {});
      }
    } catch (err: any) {
      console.warn("Camera start failed:", err);
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        setCameraError(
          "Camera access permission was denied. Please allow camera permissions in your browser or choose an image file."
        );
      } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
        setCameraError("No camera found on this device. Please upload an image file instead.");
      } else {
        setCameraError(`Camera error: ${err.message || "Could not open camera"}`);
      }
      setIsCameraActive(false);
    } finally {
      setIsStartingCamera(false);
    }
  };

  const switchCameraFacing = async () => {
    const nextFacing = facingMode === "environment" ? "user" : "environment";
    await startCamera(nextFacing);
  };

  const capturePhoto = () => {
    if (!videoRef.current) return;
    const video = videoRef.current;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const capturedFile = new File([blob], "camera-menu-scan.jpg", {
          type: "image/jpeg",
          lastModified: Date.now(),
        });
        setFile(capturedFile);
        setPreview(URL.createObjectURL(capturedFile));
        stopCamera();

        setOcrState("idle");
        setOcrText(null);
        setOcrError(null);
        setTransState("idle");
        setTranslatedText(null);
        setTransError(null);
      },
      "image/jpeg",
      0.95
    );
  };

  const retakePhoto = () => {
    setFile(null);
    setPreview(null);
    setOcrState("idle");
    setOcrText(null);
    setOcrError(null);
    setTransState("idle");
    setTranslatedText(null);
    setTransError(null);
    startCamera();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;

    if (!ALLOWED_TYPES.includes(f.type)) {
      setOcrError("Unsupported file type. Please upload a JPG, PNG, WebP, or BMP image.");
      setOcrState("error");
      return;
    }
    if (f.size > MAX_SIZE_MB * 1024 * 1024) {
      setOcrError(`File too large. Maximum allowed size is ${MAX_SIZE_MB} MB.`);
      setOcrState("error");
      return;
    }

    stopCamera();
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setOcrState("idle");
    setOcrText(null);
    setOcrError(null);
    setTransState("idle");
    setTranslatedText(null);
    setTransError(null);
  };

  const handleExtractAndTranslate = async () => {
    if (!file) return;

    // Step 1: OCR
    setOcrState("loading");
    setOcrText(null);
    setOcrError(null);
    setTransState("idle");
    setTranslatedText(null);
    setTransError(null);

    let extractedText: string | null = null;
    try {
      const result = await extractOCRText(file, ocrLang);
      if (result.text && result.text.trim()) {
        extractedText = result.text.trim();
        setOcrText(extractedText);
        setOcrEngine(result.engine);
        setOcrState("done");
      } else {
        setOcrError(result.error ?? "No readable text found in image.");
        setOcrState("error");
        return;
      }
    } catch (err: any) {
      setOcrError(err.message ?? "OCR request failed.");
      setOcrState("error");
      return;
    }

    // Step 2: Translate automatically using the currently selected targetLang
    if (!extractedText) return;
    setTransState("loading");
    setTransError(null);

    try {
      const sourceHint = ocrLang === "kan" ? "kn" : ocrLang === "eng" ? "en" : "auto";
      const result = await translateText(extractedText, targetLang, sourceHint);
      if (result.translated_text && result.translated_text.trim()) {
        setTranslatedText(result.translated_text.trim());
        setTransProvider(result.provider);
        setTransState("done");
      } else {
        setTransError(result.error ?? "Translation failed.");
        setTransState("error");
      }
    } catch (err: any) {
      setTransError(err.message ?? "Translation request failed.");
      setTransState("error");
    }
  };

  const handleRetryTranslate = async () => {
    if (!ocrText) return;
    setTransState("loading");
    setTransError(null);
    setTranslatedText(null);

    try {
      const sourceHint = ocrLang === "kan" ? "kn" : ocrLang === "eng" ? "en" : "auto";
      const result = await translateText(ocrText, targetLang, sourceHint);
      if (result.translated_text && result.translated_text.trim()) {
        setTranslatedText(result.translated_text.trim());
        setTransProvider(result.provider);
        setTransState("done");
      } else {
        setTransError(result.error ?? "Translation failed.");
        setTransState("error");
      }
    } catch (err: any) {
      setTransError(err.message ?? "Translation request failed.");
      setTransState("error");
    }
  };

  const reset = () => {
    stopCamera();
    setFile(null);
    setPreview(null);
    setOcrState("idle");
    setOcrText(null);
    setOcrError(null);
    setTransState("idle");
    setTranslatedText(null);
    setTransError(null);
    setOcrEngine(null);
    setTransProvider(null);
    setCameraError(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  const copyText = async (text: string, which: "ocr" | "trans") => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(which);
      setTimeout(() => setCopied(null), 1800);
    } catch {
    }
  };

  const langLabel =
    ocrLang === "kan"
      ? "ಕನ್ನಡ (Kannada)"
      : ocrLang === "kan+eng"
      ? "Kannada + English"
      : "English";

  const parsedItems = useMemo(
    () => parseMenuItems(ocrText, translatedText),
    [ocrText, translatedText]
  );

  return (
    <div className="rounded-2xl border bg-white dark:bg-gray-900 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-5 pt-5 pb-3 border-b border-gray-100 dark:border-gray-800">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <Camera className="h-5 w-5 text-blue-500 shrink-0" />
            <div>
              <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                Menu &amp; Signs Translation
                <p className="text-xs text-gray-500 mt-0.5">
                  Scan or upload a menu to extract and translate text.
                </p>
              </h3>
              <p className="text-xs text-gray-500 mt-0.5">
                Scan live with your camera or upload a menu photo — extract dish names, prices, and translate instantly.
              </p>
            </div>
          </div>
          {(file || isCameraActive) && (
            <button
              onClick={reset}
              className="shrink-0 text-xs text-gray-400 hover:text-red-500 flex items-center gap-1 transition-colors px-2 py-1 rounded-lg border border-transparent hover:border-gray-200 dark:hover:border-gray-700"
              title="Clear and start over"
            >
              <X className="h-3.5 w-3.5" /> Clear
            </button>
          )}
        </div>
      </div>

      <div className="p-5 space-y-5">
        {/* Step 1: Script selector + Input options */}
        <div className="space-y-3">
          {/* OCR Language selector */}
          <div className="flex items-center gap-2 flex-wrap bg-blue-50/60 dark:bg-blue-950/20 border border-blue-100 dark:border-blue-900/40 rounded-xl p-3 text-xs">
            <Languages className="h-4 w-4 text-blue-500 shrink-0" />
            <span className="font-medium text-gray-700 dark:text-gray-300">Image script:</span>
            <select
              value={ocrLang}
              onChange={(e) => setOcrLang(e.target.value)}
              className="border border-blue-200 dark:border-blue-700 rounded-lg px-2.5 py-1 text-xs bg-white dark:bg-gray-800 dark:text-white font-medium shadow-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
              aria-label="Select image script for OCR"
            >
              <option value="kan+eng">Kannada + English</option>
              <option value="kan">Kannada only </option>
              <option value="eng">English only</option>
            </select>
            <span className="text-[11px] text-gray-400 ml-auto hidden sm:block">
              {ocrLang === "kan+eng"
                ? "Bilingual engine with price preservation"
                : ocrLang === "kan"
                ? "Kannada script engine"
                : "English text engine"}
            </span>
          </div>

          {/* Action Row: Scan with Camera vs Upload File */}
          {!file && !isCameraActive && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* Scan with Camera Button */}
              <button
                type="button"
                onClick={() => startCamera("environment")}
                disabled={isStartingCamera}
                className="flex items-center justify-center gap-2 border-2 border-blue-200 dark:border-blue-800 bg-blue-50/40 hover:bg-blue-100/60 dark:bg-blue-950/30 dark:hover:bg-blue-900/40 text-blue-700 dark:text-blue-300 rounded-xl px-4 py-3.5 transition-all text-sm font-semibold shadow-sm group"
              >
                {isStartingCamera ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                    Starting Camera…
                  </>
                ) : (
                  <>
                    <Camera className="h-5 w-5 text-blue-600 group-hover:scale-110 transition-transform" />
                    <span>Scan with Camera</span>
                    <span className="text-[10px] font-normal bg-blue-200/60 dark:bg-blue-800/60 px-1.5 py-0.5 rounded text-blue-800 dark:text-blue-200">
                      Rear Cam
                    </span>
                  </>
                )}
              </button>

              {/* Upload Image Button */}
              <label className="flex-1 cursor-pointer">
                <div className="flex items-center justify-center gap-2 border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-xl px-4 py-3.5 hover:border-blue-400 transition-colors bg-gray-50/50 dark:bg-gray-800/50 text-gray-700 dark:text-gray-300 text-sm font-medium">
                  <Upload className="h-4 w-4 text-gray-500" />
                  <span>Upload Menu Photo</span>
                  <span className="text-[10px] text-gray-400">JPG, PNG, WebP</span>
                </div>
                <input
                  ref={fileRef}
                  type="file"
                  accept={ALLOWED_TYPES.join(",")}
                  onChange={handleFileChange}
                  className="sr-only"
                />
              </label>
            </div>
          )}

          {/* Camera Error Message */}
          {cameraError && (
            <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 dark:bg-amber-950/30 p-3 text-xs text-amber-800 dark:text-amber-300">
              <AlertCircle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
              <div className="flex-1">
                <p className="font-medium">Camera Notice</p>
                <p className="mt-0.5 opacity-90">{cameraError}</p>
              </div>
              <button
                onClick={() => setCameraError(null)}
                className="text-amber-600 hover:text-amber-800"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>

        {/* Live Camera Viewfinder (Google Lens style) */}
        {isCameraActive && (
          <div className="relative rounded-2xl overflow-hidden bg-black aspect-video max-h-[380px] flex items-center justify-center shadow-lg border border-gray-800">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="w-full h-full object-cover"
            />

            {/* Lens scanning frame overlay */}
            <div className="absolute inset-8 pointer-events-none border-2 border-white/40 rounded-xl flex flex-col justify-between p-2">
              <div className="flex justify-between">
                <div className="w-5 h-5 border-t-2 border-l-2 border-blue-400" />
                <div className="w-5 h-5 border-t-2 border-r-2 border-blue-400" />
              </div>
              <div className="text-center text-white/80 text-xs font-medium bg-black/50 backdrop-blur-sm self-center px-3 py-1 rounded-full">
                Align menu dishes &amp; prices inside frame
              </div>
              <div className="flex justify-between">
                <div className="w-5 h-5 border-b-2 border-l-2 border-blue-400" />
                <div className="w-5 h-5 border-b-2 border-r-2 border-blue-400" />
              </div>
            </div>

            {/* Camera Floating Controls */}
            <div className="absolute bottom-4 inset-x-0 flex items-center justify-center gap-6 z-10 px-4">
              {/* Cancel */}
              <button
                type="button"
                onClick={stopCamera}
                className="p-2.5 rounded-full bg-white/20 hover:bg-white/30 text-white backdrop-blur-md transition-colors"
                title="Cancel camera"
              >
                <X className="h-5 w-5" />
              </button>

              {/* Shutter Capture Button */}
              <button
                type="button"
                onClick={capturePhoto}
                className="h-16 w-16 rounded-full border-4 border-white bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center shadow-lg transition-transform active:scale-95"
                title="Capture photo"
              >
                <div className="h-12 w-12 rounded-full border-2 border-white/60 bg-white/20 flex items-center justify-center">
                  <Camera className="h-6 w-6 text-white" />
                </div>
              </button>

              {/* Flip Camera Facing */}
              <button
                type="button"
                onClick={switchCameraFacing}
                className="p-2.5 rounded-full bg-white/20 hover:bg-white/30 text-white backdrop-blur-md transition-colors"
                title="Switch front/rear camera"
              >
                <SwitchCamera className="h-5 w-5" />
              </button>
            </div>
          </div>
        )}

        {/* Captured / Uploaded Image Preview & Translate Action */}
        {file && !isCameraActive && (
          <div className="flex flex-col sm:flex-row gap-4 items-start bg-gray-50/60 dark:bg-gray-800/30 p-4 rounded-xl border border-gray-100 dark:border-gray-800">
            {preview && (
              <div className="relative group shrink-0 border rounded-xl overflow-hidden shadow-sm bg-black/5 max-h-48 max-w-[220px]">
                <img
                  src={preview}
                  alt="Menu preview"
                  className="max-h-48 max-w-[220px] object-contain"
                />
              </div>
            )}

            <div className="flex-1 flex flex-col gap-3 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold text-gray-800 dark:text-gray-200 truncate">
                    {file.name}
                  </p>
                  <p className="text-[11px] text-gray-500">
                    {(file.size / 1024).toFixed(0)} KB · Ready to translate
                  </p>
                </div>

                <button
                  type="button"
                  onClick={retakePhoto}
                  className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-50 transition-colors"
                  title="Retake or choose another"
                >
                  <RotateCcw className="h-3 w-3" /> Retake
                </button>
              </div>

              <div className="flex items-center gap-3 flex-wrap">
                {/* Target language selector (visible before first translate) */}
                {transState === "idle" && (
                  <div className="flex items-center gap-2">
                    <Languages className="h-3.5 w-3.5 text-gray-400 shrink-0" />
                    <LanguageSelector value={targetLang} onChange={setTargetLang} />
                  </div>
                )}

                <button
                  type="button"
                  onClick={handleExtractAndTranslate}
                  disabled={ocrState === "loading" || transState === "loading"}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-green-600 hover:bg-green-700 disabled:opacity-50 px-5 py-2.5 text-sm font-semibold text-white transition-all shadow-sm"
                >
                  {ocrState === "loading" || transState === "loading" ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      {ocrState === "loading" ? "Reading menu…" : "Translating…"}
                    </>
                  ) : (
                    <>
                      <Languages className="h-4 w-4" />
                      Translate Menu
                    </>
                  )}
                </button>

                {(ocrState === "loading" || ocrState === "done" || ocrState === "error") && (
                  <StatusBadge
                    state={ocrState}
                    label={ocrState === "loading" ? "Processing menu…" : "Extraction complete"}
                  />
                )}
              </div>
            </div>
          </div>
        )}
        {/* OCR Error Alert */}
        {ocrState === "error" && ocrError && (
          <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 dark:bg-red-950/30 dark:border-red-900/40 p-3">
            <AlertCircle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
            <div className="text-sm text-red-700 dark:text-red-400">
              <p className="font-medium mb-0.5">Text Extraction Failed</p>
              <p className="text-xs opacity-90">{ocrError}</p>
              <button
                type="button"
                onClick={handleExtractAndTranslate}
                className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-red-600 hover:underline"
              >
                <RefreshCcw className="h-3 w-3" /> Retry Extraction
              </button>
            </div>
          </div>
        )}

        {/* Output: Translation Result */}
        {transState === "loading" && (
          <div className="flex items-center gap-2 rounded-xl border border-blue-100 dark:border-blue-900/40 bg-blue-50/40 dark:bg-blue-950/20 p-4">
            <Loader2 className="h-4 w-4 animate-spin text-blue-500 shrink-0" />
            <span className="text-sm text-blue-700 dark:text-blue-300">
              {ocrState === "loading" ? "Reading menu text…" : "Translating menu…"}
            </span>
          </div>
        )}

        {transState === "done" && translatedText && (
          <div className="space-y-3">
            {/* Parsed Menu Cards View */}
            {parsedItems.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {parsedItems.map((item, idx) => (
                  <div
                    key={idx}
                    className="flex items-start justify-between gap-3 p-3 rounded-xl border border-gray-100 dark:border-gray-800 bg-gray-50/70 dark:bg-gray-800/40 hover:border-blue-200 transition-colors"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-sm text-gray-900 dark:text-gray-100">
                        {item.translatedName || item.originalName}
                      </p>
                    </div>
                    <span className="shrink-0 text-xs font-bold px-2.5 py-1 rounded-lg bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
                      {item.price}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Full Translation Text */}
            <div className="flex flex-col rounded-xl border border-green-100 dark:border-green-900/40 bg-green-50/40 dark:bg-green-950/20 overflow-hidden">
              <div className="flex items-center justify-between px-3 py-2 bg-green-100/60 dark:bg-green-900/30 border-b border-green-100 dark:border-green-900/40">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-xs font-semibold text-green-700 dark:text-green-300">
                    Translated Menu
                  </span>
                  {transProvider && (
                    <span className="text-[10px] text-green-600 bg-green-100 dark:bg-green-900/50 px-1.5 py-0.5 rounded font-medium">
                      via {transProvider}
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => copyText(translatedText, "trans")}
                  className="text-[10px] text-green-600 hover:text-green-800 flex items-center gap-1 font-medium"
                >
                  <Copy className="h-3 w-3" />
                  {copied === "trans" ? "Copied!" : "Copy"}
                </button>
              </div>
              <pre className="whitespace-pre-wrap font-sans text-sm text-gray-800 dark:text-gray-100 leading-relaxed p-3 overflow-auto max-h-72">
                {translatedText}
              </pre>
              <p className="text-[10px] text-gray-400 px-3 pb-2">
                Prices and quantities are preserved from the original extraction.
              </p>
            </div>

            {/* Re-translate with a different language */}
            <div className="flex items-center gap-2 flex-wrap pt-1">
              <Languages className="h-4 w-4 text-gray-400 shrink-0" />
              <span className="text-xs text-gray-500">Translate to another language:</span>
              <LanguageSelector value={targetLang} onChange={setTargetLang} />
              <button
                type="button"
                onClick={handleRetryTranslate}
                disabled={transState === "loading"}
                className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-1.5 text-xs font-semibold text-gray-700 dark:text-gray-200 hover:bg-gray-50 disabled:opacity-50 transition-colors"
              >
                <RefreshCcw className="h-3 w-3" /> Re-translate
              </button>
            </div>
          </div>
        )}

        {/* Translation Error & Retry Path */}
        {transState === "error" && transError && (
          <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 dark:bg-red-950/30 p-3">
            <AlertCircle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
            <div className="text-sm text-red-700 dark:text-red-400 flex-1">
              <p className="font-medium mb-0.5">Translation Failed</p>
              <p className="text-xs opacity-90">{transError}</p>
              <button
                type="button"
                onClick={handleRetryTranslate}
                className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-red-600 hover:text-red-800 underline"
              >
                <RefreshCcw className="h-3 w-3" /> Retry Translation
              </button>
            </div>
          </div>
        )}

        {/* Informational Footer Note */}
        {!file && !isCameraActive && (
          <p className="text-xs text-gray-400 border-t pt-3 flex items-start gap-1.5">
            <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0 text-blue-400" />
            <span>
              <strong>Menu OCR Tip:</strong> Point camera steadily at the printed menu or upload a clear photo.
              Original dish boundaries and prices are strictly preserved.
            </span>
          </p>
        )}
      </div>
    </div>
  );
};
