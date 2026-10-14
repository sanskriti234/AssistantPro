import type { EnrollmentResult } from '../types';
import { request } from './client';

export const REQUIRED_SAMPLES = 20;

// Runs the backend's SCRFD detection + quality check on one captured frame.
export async function validateSample(frameDataUrl: string): Promise<{ accepted: boolean; reason?: string }> {
  return request('/enrollment/validate-sample', { body: { frame: frameDataUrl } });
}

// Backend's final step: AdaFace embedding generation from accepted samples.
// LIMITATION: this frontend does not currently collect per-sample embedding
// vectors (no real AdaFace model runs client-side, by design - the backend
// owns the ML pipeline). Only the counts are sent; the backend accepts an
// optional `embeddings` array for when a real capture pipeline supplies it.
export async function finalizeEnrollment(_studentId: string, validSampleCount: number): Promise<EnrollmentResult> {
  return request('/enrollment/finalize', { body: { validSampleCount, embeddings: [] } });
}
