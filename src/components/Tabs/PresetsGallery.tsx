import { memo, useCallback, useMemo, useRef, useState } from 'react';
import { Copy } from 'lucide-react';

import { Button } from '../controls/Button';
import { Select, TextField } from '../controls/Inputs';
import { Modal } from '../Modal';
import { SvgCanvas } from '../SvgCanvas';
import {
  BUILTIN_PRESET_NAMES,
  DEFAULT_PHRASE,
  nextPresetName,
  presetsFromJson,
  presetsToJson,
} from '../../data/presets';
import { downloadFont, downloadJson, downloadSvg, readTextFile } from '../../engine/download';
import { FONT_FAMILY, styleSlug } from '../../engine/fontNaming';
import { renderTextSvg } from '../../engine/geometry';
import { usePresetContext } from '../../hooks/usePresetContext';
import type { RenderContext, StyleParams } from '../../types/fontTypes';
import { saveAs } from 'file-saver';

const PRESETS_FILENAME = 'Compresso_Font_Studio_Presets.json';

/** Card specimens use a light background when the card is active. */
const ACTIVE_CARD_COLORS = { fill: '#000000', stroke: '#000000', background: '#FFFFFF' };
const IDLE_CARD_COLORS = { fill: '#FFFFFF', stroke: '#FFFFFF', background: '#0C0C0C' };

interface PresetsGalleryProps {
  presets: Record<string, StyleParams>;
  activePreset: string;
  context: RenderContext;
  onApply: (name: string) => void;
  onSave: () => void;
  onCreate: (name: string, source?: StyleParams, activate?: boolean) => string | null;
  onCreateDefault: (name: string) => string | null;
  onDelete: (name: string) => void;
  onReset: () => void;
  onImport: (presets: Record<string, StyleParams>, active: string | null) => void;
}

export function PresetsGallery({
  presets,
  activePreset,
  context,
  onApply,
  onSave,
  onCreate,
  onCreateDefault,
  onDelete,
  onReset,
  onImport,
}: PresetsGalleryProps) {
  const [newName, setNewName] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const importRef = useRef<HTMLInputElement>(null);

  const names = useMemo(() => Object.keys(presets), [presets]);
  const suggestedName = useMemo(() => nextPresetName(names), [names]);

  const resolveName = useCallback(
    () => newName.trim() || nextPresetName(names),
    [names, newName],
  );

  const handleCreate = useCallback(() => {
    const name = resolveName();
    const error = onCreate(name);
    if (error) {
      setMessage(error);
      return;
    }
    setMessage(`Начертание «${name}» создано и стало активным`);
    setNewName('');
  }, [onCreate, resolveName]);

  const handleCreateDefault = useCallback(() => {
    const name = resolveName();
    const error = onCreateDefault(name);
    if (error) {
      setMessage(error);
      return;
    }
    setMessage(`Начертание «${name}» создано с настройками Regular`);
    setNewName('');
  }, [onCreateDefault, resolveName]);

  const handleCopyCard = useCallback(
    (sourceName: string) => {
      const source = presets[sourceName];
      if (!source) {
        return;
      }
      const name = nextPresetName(names);
      const error = onCreate(name, source, false);
      if (error) {
        setMessage(error);
        return;
      }
      setMessage(`Настройки «${sourceName}» скопированы в «${name}»`);
    },
    [names, onCreate, presets],
  );

  const handleSave = useCallback(() => {
    onSave();
    setMessage(`Изменения записаны в «${activePreset}»`);
  }, [activePreset, onSave]);

  const handleReset = useCallback(() => {
    onReset();
    setMessage('Параметры сброшены к Regular');
  }, [onReset]);

  const handleExport = useCallback(() => {
    downloadJson(presetsToJson(presets, activePreset), PRESETS_FILENAME);
    setMessage(`Библиотека сохранена: ${PRESETS_FILENAME}`);
  }, [activePreset, presets]);

  const handleImport = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }
      try {
        const parsed = presetsFromJson(await readTextFile(file));
        onImport(parsed.presets, parsed.active);
        setMessage(`Загружено начертаний: ${Object.keys(parsed.presets).length}`);
      } catch (error) {
        setMessage(
          `Не удалось прочитать файл: ${error instanceof Error ? error.message : String(error)}`,
        );
      } finally {
        event.target.value = '';
      }
    },
    [onImport],
  );

  const confirmDelete = useCallback(() => {
    if (pendingDelete) {
      onDelete(pendingDelete);
      setMessage(`Начертание «${pendingDelete}» удалено`);
      setPendingDelete(null);
    }
  }, [onDelete, pendingDelete]);

  const exportSvg = useCallback(() => {
    const full = renderTextSvg(DEFAULT_PHRASE, context, 1);
    downloadSvg(full, `${styleSlug(activePreset)}-specimen.svg`);
    setMessage('SVG сохранён');
  }, [activePreset, context]);

  const exportFont = useCallback(async () => {
    setBusy(true);
    setMessage('Сборка шрифта…');
    try {
      const { buildFontBinary } = await import('../../engine/opentypeExporter');
      const font = buildFontBinary(context, {
        family: FONT_FAMILY,
        styleName: activePreset,
      });
      downloadFont(font.binary, font.filename);
      setMessage(
        `Шрифт собран: ${font.filename}` +
          (font.kernPairCount > 0 ? ` · кернинг ${font.kernPairCount} пар` : ''),
      );
    } catch (error) {
      setMessage(
        `Ошибка сборки шрифта: ${error instanceof Error ? error.message : String(error)}`,
      );
    } finally {
      setBusy(false);
    }
  }, [activePreset, context]);

  const exportFamily = useCallback(async () => {
    setBusy(true);
    setMessage('Сборка архива…');
    try {
      const { FAMILY_PACK_FILENAME, buildFamilyPack } = await import(
        '../../engine/zipExporter'
      );
      const blob = await buildFamilyPack(presets, {
        family: FONT_FAMILY,
        specimen: DEFAULT_PHRASE,
        onProgress: (done, total, styleName) => {
          setMessage(`Начертание ${done} из ${total}: ${styleName}`);
        },
      });
      saveAs(blob, FAMILY_PACK_FILENAME);
      setMessage(`Архив собран: ${FAMILY_PACK_FILENAME}`);
    } catch (error) {
      setMessage(
        `Ошибка сборки архива: ${error instanceof Error ? error.message : String(error)}`,
      );
    } finally {
      setBusy(false);
    }
  }, [presets]);

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="flex flex-wrap items-end gap-2 rounded-lg border border-studio-border bg-studio-surface p-3">
        <div className="w-[210px]">
          <Select
            label="Начертание"
            value={activePreset}
            options={names}
            onChange={onApply}
          />
        </div>
        <Button onClick={handleSave}>Сохранить изменения</Button>
        <Button onClick={handleReset}>Сбросить к Regular</Button>
        <div className="w-[210px]">
          <TextField
            label="Имя нового начертания"
            value={newName}
            placeholder={suggestedName}
            onChange={setNewName}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                handleCreate();
              }
            }}
          />
        </div>
        <Button variant="primary" onClick={handleCreate}>
          Создать из текущих настроек
        </Button>
        <Button onClick={handleCreateDefault}>Создать с настройками по умолчанию</Button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {names.map((name) => (
            <PresetCard
              key={name}
              name={name}
              params={presets[name]}
              specimen={DEFAULT_PHRASE}
              active={name === activePreset}
              deletable={!BUILTIN_PRESET_NAMES.includes(name)}
              onApply={onApply}
              onCopy={handleCopyCard}
              onRequestDelete={setPendingDelete}
            />
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-studio-border pt-3">
        <Button onClick={exportSvg} disabled={busy}>
          Экспорт SVG
        </Button>
        <Button onClick={() => void exportFont()} disabled={busy} variant="primary">
          Скачать шрифт (OTF)
        </Button>
        <Button onClick={() => void exportFamily()} disabled={busy}>
          Экспорт семейства (ZIP)
        </Button>
        <Button onClick={handleExport} disabled={busy}>
          Скачать пресеты (JSON)
        </Button>
        <Button onClick={() => importRef.current?.click()} disabled={busy}>
          Загрузить пресеты (JSON)
        </Button>
        <input
          ref={importRef}
          type="file"
          accept=".json,application/json"
          className="hidden"
          onChange={(event) => void handleImport(event)}
        />
        {message ? (
          <span className="font-mono text-[11px] text-studio-muted">{message}</span>
        ) : null}
      </div>

      {pendingDelete ? (
        <Modal
          title="Удаление начертания"
          onClose={() => setPendingDelete(null)}
          actions={
            <>
              <Button onClick={() => setPendingDelete(null)}>Отмена</Button>
              <Button variant="danger" onClick={confirmDelete}>
                Да, удалить
              </Button>
            </>
          }
        >
          Вы точно хотите удалить начертание «{pendingDelete}»? Это действие нельзя
          отменить.
        </Modal>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */

interface PresetCardProps {
  name: string;
  params: StyleParams;
  specimen: string;
  active: boolean;
  deletable: boolean;
  onApply: (name: string) => void;
  onCopy: (name: string) => void;
  onRequestDelete: (name: string) => void;
}

const PresetCard = memo(function PresetCard({
  name,
  params,
  specimen,
  active,
  deletable,
  onApply,
  onCopy,
  onRequestDelete,
}: PresetCardProps) {
  const cardParams = useMemo<StyleParams>(
    () => ({
      ...params,
      ...(active ? ACTIVE_CARD_COLORS : IDLE_CARD_COLORS),
      showGrid: false,
      showGuides: false,
    }),
    [params, active],
  );

  const context = usePresetContext(cardParams);

  const svg = useMemo(
    () =>
      context
        ? renderTextSvg(specimen, context, 1, { paintBackground: false, contain: true })
        : '',
    [context, specimen],
  );

  const apply = () => onApply(name);

  return (
    <article
      className={
        'flex cursor-pointer flex-col gap-2.5 rounded-lg border p-3 text-left transition-colors ' +
        (active
          ? 'border-white bg-white'
          : 'border-studio-border bg-studio-surface hover:border-studio-border-strong')
      }
      onClick={apply}
    >
      <div className="flex items-baseline justify-between gap-2">
        <h3
          className={
            'truncate text-[13px] font-semibold ' + (active ? 'text-black' : 'text-studio-text')
          }
          title={name}
        >
          {name}
        </h3>
        {active ? (
          <span className="shrink-0 text-[10px] font-semibold tracking-wide text-black uppercase">
            ● Активно
          </span>
        ) : null}
      </div>

      <div
        className={
          'h-[104px] w-full overflow-hidden rounded ' + (active ? 'bg-white' : 'bg-studio-bg')
        }
      >
        {svg ? (
          <SvgCanvas svg={svg} fluid />
        ) : (
          <span className="flex h-full items-center justify-center text-[10px] text-studio-faint">
            загрузка контуров…
          </span>
        )}
      </div>

      <div className="mt-auto flex gap-1.5">
        <Button
          compact
          variant={active ? 'inverted' : 'default'}
          title="Скопировать настройки"
          onClick={(event) => {
            event.stopPropagation();
            onCopy(name);
          }}
        >
          <Copy size={14} aria-hidden />
        </Button>
        <Button
          compact
          variant={active ? 'inverted' : 'default'}
          disabled={!deletable}
          title={
            deletable
              ? `Удалить начертание ${name}`
              : 'Заводское начертание нельзя удалить'
          }
          onClick={(event) => {
            event.stopPropagation();
            onRequestDelete(name);
          }}
        >
          Удалить
        </Button>
      </div>
    </article>
  );
});
