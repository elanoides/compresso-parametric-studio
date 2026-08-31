/**
 * Studio state: the live style, the preset library and the asynchronously
 * loaded font outlines that font-symbol modules need.
 *
 * Everything lives in the browser — the preset library is mirrored into
 * localStorage so a reload keeps the user's work.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  DEFAULT_INSPECT_CHAR,
  DEFAULT_PHRASE,
  DEFAULT_PRESET_NAME,
  REGULAR_PARAMS,
  freshPresetLibrary,
  normalizeParams,
} from '../data/presets';
import { resolveFontPathsFor } from '../engine/renderContext';
import type { RenderContext, StyleParams, TabId } from '../types/fontTypes';

const STORAGE_KEY = 'crt-font-studio/v3';

interface PersistedState {
  presets: Record<string, StyleParams>;
  activePreset: string;
  params: StyleParams;
  wordText: string;
  previewScale: number;
  inspectChar: string;
}

function loadPersisted(): PersistedState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<PersistedState>;
    if (!parsed.presets || typeof parsed.presets !== 'object') {
      return null;
    }
    const presets: Record<string, StyleParams> = {};
    for (const [name, params] of Object.entries(parsed.presets)) {
      presets[name] = normalizeParams(params);
    }
    // Factory styles are always available even if an old payload lacked them.
    const merged = { ...freshPresetLibrary(), ...presets };
    return {
      presets: merged,
      activePreset:
        typeof parsed.activePreset === 'string' && merged[parsed.activePreset]
          ? parsed.activePreset
          : DEFAULT_PRESET_NAME,
      params: normalizeParams(parsed.params ?? merged[DEFAULT_PRESET_NAME]),
      wordText: typeof parsed.wordText === 'string' ? parsed.wordText : DEFAULT_PHRASE,
      previewScale:
        typeof parsed.previewScale === 'number' && Number.isFinite(parsed.previewScale)
          ? parsed.previewScale
          : 0.38,
      inspectChar:
        typeof parsed.inspectChar === 'string' && parsed.inspectChar
          ? parsed.inspectChar
          : DEFAULT_INSPECT_CHAR,
    };
  } catch {
    return null;
  }
}

export interface Studio {
  tab: TabId;
  setTab: (tab: TabId) => void;

  params: StyleParams;
  updateParams: (patch: Partial<StyleParams>) => void;
  setParams: (next: StyleParams) => void;

  presets: Record<string, StyleParams>;
  activePreset: string;
  applyPreset: (name: string) => void;
  saveActivePreset: () => void;
  createPreset: (name: string) => string | null;
  deletePreset: (name: string) => void;
  replaceLibrary: (presets: Record<string, StyleParams>, active: string | null) => void;
  resetToRegular: () => void;

  wordText: string;
  setWordText: (text: string) => void;
  previewScale: number;
  setPreviewScale: (scale: number) => void;
  inspectChar: string;
  setInspectChar: (ch: string) => void;

  /** Render context for the live style. */
  context: RenderContext;
  fontLoading: boolean;
  fontError: string | null;
}

export function useStudio(): Studio {
  const initial = useMemo(() => loadPersisted(), []);

  const [tab, setTab] = useState<TabId>('word');
  const [presets, setPresetsState] = useState<Record<string, StyleParams>>(
    () => initial?.presets ?? freshPresetLibrary(),
  );
  const [activePreset, setActivePreset] = useState<string>(
    () => initial?.activePreset ?? DEFAULT_PRESET_NAME,
  );
  const [params, setParamsState] = useState<StyleParams>(
    () => initial?.params ?? { ...REGULAR_PARAMS },
  );
  const [wordText, setWordText] = useState(() => initial?.wordText ?? DEFAULT_PHRASE);
  const [previewScale, setPreviewScale] = useState(() => initial?.previewScale ?? 0.38);
  const [inspectChar, setInspectChar] = useState(
    () => initial?.inspectChar ?? DEFAULT_INSPECT_CHAR,
  );

  const [fontPaths, setFontPaths] = useState<Readonly<Record<string, string>>>({});
  const [fontAlphabet, setFontAlphabet] = useState('');
  const [fontLoading, setFontLoading] = useState(false);
  const [fontError, setFontError] = useState<string | null>(null);

  /* ---- persistence -------------------------------------------------- */

  const persistTimer = useRef<number | null>(null);
  useEffect(() => {
    if (persistTimer.current !== null) {
      window.clearTimeout(persistTimer.current);
    }
    persistTimer.current = window.setTimeout(() => {
      try {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({
            presets,
            activePreset,
            params,
            wordText,
            previewScale,
            inspectChar,
          }),
        );
      } catch {
        // Quota exceeded or storage disabled — the session still works.
      }
    }, 400);
    return () => {
      if (persistTimer.current !== null) {
        window.clearTimeout(persistTimer.current);
      }
    };
  }, [presets, activePreset, params, wordText, previewScale, inspectChar]);

  /* ---- font outlines ------------------------------------------------ */

  const fontRequestKey = `${params.moduleType}|${params.moduleFontSubfamily}|${params.moduleFontWeight}|${params.moduleFontChars}`;

  useEffect(() => {
    let cancelled = false;
    setFontError(null);

    if (params.moduleType !== 'font_symbols') {
      setFontPaths({});
      setFontAlphabet('');
      setFontLoading(false);
      return;
    }

    setFontLoading(true);
    resolveFontPathsFor(params)
      .then((resolved) => {
        if (cancelled) {
          return;
        }
        setFontPaths(resolved.paths);
        setFontAlphabet(resolved.alphabet);
        if (!resolved.filename) {
          setFontError('Шрифт для выбранного начертания не найден');
        } else if (Object.keys(resolved.paths).length === 0) {
          setFontError('В выбранном шрифте не найдено подходящих символов');
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setFontError(error instanceof Error ? error.message : 'Ошибка загрузки шрифта');
          setFontPaths({});
          setFontAlphabet('');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setFontLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
    // Params object identity changes on every slider move; the key captures the
    // only fields that can invalidate the loaded outlines.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fontRequestKey]);

  /* ---- actions ------------------------------------------------------ */

  const updateParams = useCallback((patch: Partial<StyleParams>) => {
    setParamsState((prev) => ({ ...prev, ...patch }));
  }, []);

  const setParams = useCallback((next: StyleParams) => {
    setParamsState(next);
  }, []);

  const applyPreset = useCallback(
    (name: string) => {
      setPresetsState((library) => {
        const target = library[name];
        if (target) {
          setParamsState({ ...target });
          setActivePreset(name);
        }
        return library;
      });
    },
    [],
  );

  const saveActivePreset = useCallback(() => {
    setPresetsState((library) => ({ ...library, [activePreset]: { ...params } }));
  }, [activePreset, params]);

  const createPreset = useCallback(
    (rawName: string): string | null => {
      const name = rawName.trim();
      if (!name) {
        return 'Введите имя начертания';
      }
      let conflict = false;
      setPresetsState((library) => {
        if (library[name]) {
          conflict = true;
          return library;
        }
        return { ...library, [name]: { ...params } };
      });
      if (conflict) {
        return `Начертание «${name}» уже существует`;
      }
      setActivePreset(name);
      return null;
    },
    [params],
  );

  const deletePreset = useCallback((name: string) => {
    setPresetsState((library) => {
      if (!library[name]) {
        return library;
      }
      const next = { ...library };
      delete next[name];
      setActivePreset((current) => {
        if (current !== name) {
          return current;
        }
        const fallback = next[DEFAULT_PRESET_NAME] ? DEFAULT_PRESET_NAME : Object.keys(next)[0];
        if (fallback) {
          setParamsState({ ...next[fallback] });
        }
        return fallback ?? DEFAULT_PRESET_NAME;
      });
      return next;
    });
  }, []);

  const replaceLibrary = useCallback(
    (imported: Record<string, StyleParams>, active: string | null) => {
      setPresetsState((library) => {
        const merged = { ...library, ...imported };
        const target = active && merged[active] ? active : null;
        if (target) {
          setActivePreset(target);
          setParamsState({ ...merged[target] });
        }
        return merged;
      });
    },
    [],
  );

  const resetToRegular = useCallback(() => {
    setParamsState({ ...REGULAR_PARAMS });
    setPresetsState((library) => ({ ...library, Regular: { ...REGULAR_PARAMS } }));
    setActivePreset(DEFAULT_PRESET_NAME);
  }, []);

  const context = useMemo<RenderContext>(
    () => ({ params, fontPaths, fontAlphabet }),
    [params, fontPaths, fontAlphabet],
  );

  return {
    tab,
    setTab,
    params,
    updateParams,
    setParams,
    presets,
    activePreset,
    applyPreset,
    saveActivePreset,
    createPreset,
    deletePreset,
    replaceLibrary,
    resetToRegular,
    wordText,
    setWordText,
    previewScale,
    setPreviewScale,
    inspectChar,
    setInspectChar,
    context,
    fontLoading,
    fontError,
  };
}
