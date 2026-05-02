/**
 * BarcodeScanButton — Plan v4 §10 tablet productivity tool.
 *
 * Tap-to-scan affordance for tablet operators. Wraps the browser's
 * `BarcodeDetector` API (Chromium + Safari iOS 17+) when available;
 * gracefully hides itself otherwise so an unsupported device doesn't
 * see a broken button.
 *
 * Use case: the operator scans a Production Order's QR/Code-128
 * barcode glued to the boat hull. The decoded string flows into
 * whatever input the parent listens to (typically the OrderId
 * field on `IssueForm`). No camera permission flow built into this
 * component — `getUserMedia({video: true})` triggers the browser's
 * native prompt the first time.
 *
 * Progressive enhancement contract:
 *   * `BarcodeDetector` undefined → component returns `null`,
 *     parent's grid simply collapses one column.
 *   * Camera permission denied → component returns `null` after
 *     the first attempt + emits `onError` so the parent can show
 *     a hint elsewhere.
 *   * Otherwise → button opens the camera, scans for ~10s, calls
 *     `onScan(value)` on first match, closes the camera.
 *
 * Supported formats default to the codes NELO uses on the floor:
 * Code 128 (orders), QR (operations + workers).
 *
 * Sprint Q.13.C / C.3.5.
 */

import { useEffect, useRef, useState } from 'react';
import { Camera, Loader2, X } from 'lucide-react';

type BarcodeFormat =
  | 'code_128'
  | 'code_39'
  | 'ean_13'
  | 'ean_8'
  | 'qr_code'
  | 'upc_a'
  | 'upc_e'
  | 'data_matrix';

interface BarcodeDetectorOptions {
  formats?: BarcodeFormat[];
}

interface DetectedBarcode {
  rawValue: string;
  format: string;
}

declare global {
  interface Window {
    BarcodeDetector?: {
      new (opts?: BarcodeDetectorOptions): {
        detect(image: ImageBitmapSource): Promise<DetectedBarcode[]>;
      };
    };
  }
}

export interface BarcodeScanButtonProps {
  onScan: (value: string) => void;
  onError?: (message: string) => void;
  /**
   * Formats to try — defaults to NELO floor codes. Pass a smaller
   * set when the consumer only wants QR (faster detection).
   */
  formats?: BarcodeFormat[];
  className?: string;
  /** Button label; defaults to "Scan". */
  label?: string;
}

const _isBarcodeDetectorAvailable = () =>
  typeof window !== 'undefined' && typeof window.BarcodeDetector === 'function';

export function BarcodeScanButton({
  onScan,
  onError,
  formats = ['code_128', 'qr_code'],
  className = '',
  label = 'Scan',
}: BarcodeScanButtonProps) {
  const [open, setOpen] = useState(false);
  const [scanning, setScanning] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const cancelRef = useRef(false);

  // Hide the button entirely on unsupported browsers — calling code
  // doesn't have to feature-detect.
  if (!_isBarcodeDetectorAvailable()) {
    return null;
  }

  const stopCamera = () => {
    cancelRef.current = true;
    setScanning(false);
    setOpen(false);
    if (streamRef.current) {
      for (const track of streamRef.current.getTracks()) {
        track.stop();
      }
      streamRef.current = null;
    }
  };

  // Cleanup on unmount: ensure no orphan camera tracks.
  useEffect(() => {
    return () => stopCamera();
  }, []);

  const startScan = async () => {
    if (!_isBarcodeDetectorAvailable()) return;
    cancelRef.current = false;
    setOpen(true);
    setScanning(true);

    const Detector = window.BarcodeDetector!;
    const detector = new Detector({ formats });

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
        audio: false,
      });
    } catch (err) {
      onError?.(
        err instanceof Error ? err.message : 'Câmara indisponível.',
      );
      stopCamera();
      return;
    }
    streamRef.current = stream;
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      await videoRef.current.play().catch(() => undefined);
    }

    // Poll the detector at ~10 fps until we hit a match or 15s elapse.
    const start = Date.now();
    const TIMEOUT_MS = 15_000;
    const tick = async () => {
      if (cancelRef.current) return;
      if (Date.now() - start > TIMEOUT_MS) {
        onError?.('Sem código detectado em 15s. Tenta de novo.');
        stopCamera();
        return;
      }
      const video = videoRef.current;
      if (video && video.readyState >= 2) {
        try {
          const results = await detector.detect(video);
          if (results.length > 0) {
            const value = results[0].rawValue.trim();
            if (value) {
              onScan(value);
              stopCamera();
              return;
            }
          }
        } catch {
          // Detector may throw when the video frame isn't ready yet
          // (race on first paints). Quietly retry.
        }
      }
      setTimeout(tick, 100);
    };
    setTimeout(tick, 200);
  };

  return (
    <>
      <button
        type="button"
        onClick={startScan}
        disabled={open}
        className={`inline-flex items-center justify-center gap-2 min-h-[56px] px-4 rounded-xl bg-accent/15 text-accent hover:bg-accent/25 transition-colors disabled:opacity-50 ${className}`}
      >
        {scanning ? (
          <Loader2 className="w-5 h-5 animate-spin" />
        ) : (
          <Camera className="w-5 h-5" />
        )}
        <span className="font-medium">{label}</span>
      </button>

      {open ? (
        <div className="fixed inset-0 z-[60] bg-black/80 flex items-center justify-center p-4">
          <div className="relative w-full max-w-lg aspect-square bg-black rounded-2xl overflow-hidden">
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className="w-full h-full object-cover"
            />
            {/* Targeting frame */}
            <div className="absolute inset-12 border-2 border-accent/70 rounded-xl pointer-events-none" />
            <button
              type="button"
              onClick={stopCamera}
              className="absolute top-3 right-3 p-3 rounded-full bg-black/60 text-white hover:bg-black/80 min-h-[56px] min-w-[56px] flex items-center justify-center"
              title="Cancelar"
            >
              <X size={22} />
            </button>
            <p className="absolute bottom-4 left-0 right-0 text-center text-white/80 text-sm">
              Aponta a câmara para o código de barras / QR.
            </p>
          </div>
        </div>
      ) : null}
    </>
  );
}
