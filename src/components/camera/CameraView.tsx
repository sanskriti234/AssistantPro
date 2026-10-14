import { type RefObject } from 'react';

export function CameraView({
  videoRef,
  ready,
  error,
  aspect = 'aspect-[3/4]',
  guideLabel,
}: {
  videoRef: RefObject<HTMLVideoElement | null>;
  ready: boolean;
  error: string | null;
  aspect?: string;
  guideLabel?: string;
}) {
  return (
    <div className={`relative w-full ${aspect} rounded-2xl overflow-hidden bg-surface-2 border border-border-soft`}>
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="w-full h-full object-cover scale-x-[-1]"
      />

      {!ready && !error && (
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="text-xs text-text-dim font-mono">Requesting camera access…</p>
        </div>
      )}

      {error && (
        <div className="absolute inset-0 flex items-center justify-center px-6 text-center">
          <p className="text-xs text-blocked">{error}</p>
        </div>
      )}

      {ready && (
        <>
          <div className="absolute inset-0 pointer-events-none">
            <span className="scan-corner absolute top-8 left-8 border-t-2 border-l-2 rounded-tl-md" />
            <span className="scan-corner absolute top-8 right-8 border-t-2 border-r-2 rounded-tr-md" style={{ animationDelay: '0.2s' }} />
            <span className="scan-corner absolute bottom-8 left-8 border-b-2 border-l-2 rounded-bl-md" style={{ animationDelay: '0.4s' }} />
            <span className="scan-corner absolute bottom-8 right-8 border-b-2 border-r-2 rounded-br-md" style={{ animationDelay: '0.6s' }} />
          </div>
          {guideLabel && (
            <div className="absolute bottom-4 inset-x-0 text-center">
              <span className="font-mono text-[11px] text-text-dim bg-base/60 px-2.5 py-1 rounded-full">{guideLabel}</span>
            </div>
          )}
        </>
      )}
    </div>
  );
}
