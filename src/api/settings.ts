import type { SystemSettings } from '../types';
import { request } from './client';

export async function fetchSettings(): Promise<SystemSettings> {
  return request('/settings');
}

export async function updateSettings(update: Partial<SystemSettings>): Promise<SystemSettings> {
  return request('/settings', { method: 'PUT', body: update });
}
