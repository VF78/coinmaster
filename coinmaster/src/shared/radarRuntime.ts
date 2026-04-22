import type { RadarRuntimeSettings } from './dto.js';

export const DEFAULT_RADAR_RUNTIME_SETTINGS: RadarRuntimeSettings = {
  enabled: true,
  autoConfirm: false,
};

export function cloneRadarRuntimeDefaults(): RadarRuntimeSettings {
  return { ...DEFAULT_RADAR_RUNTIME_SETTINGS };
}

export function normalizeRadarRuntimeSettings(
  input: unknown,
  fallbackAutoConfirm = DEFAULT_RADAR_RUNTIME_SETTINGS.autoConfirm,
): RadarRuntimeSettings {
  const raw = (input && typeof input === 'object') ? (input as Record<string, unknown>) : {};
  return {
    enabled: raw.enabled !== false,
    autoConfirm: raw.autoConfirm !== undefined ? Boolean(raw.autoConfirm) : Boolean(fallbackAutoConfirm),
  };
}
