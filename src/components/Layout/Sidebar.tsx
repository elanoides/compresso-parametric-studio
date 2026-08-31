import { useCallback, useRef, useState } from 'react';

import { Accordion } from './Accordion';
import { Button } from '../controls/Button';
import { Checkbox, ColorField, FieldLabel, RadioGroup, Select, TextField } from '../controls/Inputs';
import { Slider } from '../controls/Slider';
import { MODULE_FONT_SUBFAMILIES, weightsForSubfamily } from '../../data/moduleFontCatalog';
import { parseCustomSvg, serializeStamp } from '../../engine/moduleStamp';
import {
  FILL_ORDER_COLUMNS,
  FILL_ORDER_ROWS,
  MODULE_CUSTOM_SVG,
  MODULE_FONT,
  MODULE_OVAL,
  type FillOrder,
  type ModuleType,
  type StyleParams,
} from '../../types/fontTypes';

const MODULE_ANGLE_PRESETS = [0, 45, -45, 90] as const;

const MODULE_TYPE_OPTIONS: ReadonlyArray<{ value: ModuleType; label: string }> = [
  { value: MODULE_OVAL, label: 'Овал' },
  { value: MODULE_CUSTOM_SVG, label: 'Кастомный SVG' },
  { value: MODULE_FONT, label: 'Символы шрифта' },
];

const FILL_ORDER_OPTIONS: ReadonlyArray<{ value: FillOrder; label: string }> = [
  { value: FILL_ORDER_COLUMNS, label: 'Сверху вниз (по колонкам)' },
  { value: FILL_ORDER_ROWS, label: 'Слева направо (по строкам)' },
];

interface SidebarProps {
  params: StyleParams;
  onChange: (patch: Partial<StyleParams>) => void;
  fontLoading: boolean;
  fontError: string | null;
  presets: Record<string, StyleParams>;
  activePreset: string;
  onApplyPreset: (name: string) => void;
  onSavePreset: () => void;
  onResetPreset: () => void;
}

export function Sidebar({
  params,
  onChange,
  fontLoading,
  fontError,
  presets,
  activePreset,
  onApplyPreset,
  onSavePreset,
  onResetPreset,
}: SidebarProps) {
  return (
    <aside className="flex w-[300px] shrink-0 flex-col gap-2 overflow-y-auto border-r border-studio-border bg-studio-bg p-3">
      <PresetDock
        names={Object.keys(presets)}
        activePreset={activePreset}
        onApply={onApplyPreset}
        onSave={onSavePreset}
        onReset={onResetPreset}
      />
      <ModuleSection
        params={params}
        onChange={onChange}
        fontLoading={fontLoading}
        fontError={fontError}
      />
      <SpacingSection params={params} onChange={onChange} />
      <DeformSection params={params} onChange={onChange} />
      <KerningSection params={params} onChange={onChange} />
      <ColorSection params={params} onChange={onChange} />
    </aside>
  );
}

interface StyleSectionProps {
  params: StyleParams;
  onChange: (patch: Partial<StyleParams>) => void;
  fontLoading: boolean;
  fontError: string | null;
}

function PresetDock({
  names,
  activePreset,
  onApply,
  onSave,
  onReset,
}: {
  names: readonly string[];
  activePreset: string;
  onApply: (name: string) => void;
  onSave: () => void;
  onReset: () => void;
}) {
  return (
    <div className="rounded-lg border border-studio-border bg-studio-surface p-2.5">
      <Select
        label="Начертание"
        value={activePreset}
        options={names}
        onChange={onApply}
      />
      <div className="mt-2 grid grid-cols-2 gap-1.5">
        <Button compact onClick={onSave} title="Перезаписать активное начертание текущими параметрами">
          Сохранить
        </Button>
        <Button compact onClick={onReset} title="Вернуть параметры Regular">
          Сбросить к Regular
        </Button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

function ModuleSection({ params, onChange, fontLoading, fontError }: StyleSectionProps) {
  return (
    <Accordion title="Модуль" defaultOpen>
      <RadioGroup<ModuleType>
        label="Тип модуля"
        value={params.moduleType}
        options={MODULE_TYPE_OPTIONS}
        onChange={(moduleType) => onChange({ moduleType })}
      />

      <Slider
        label={params.moduleType === MODULE_FONT ? 'Ширина ячейки (rx)' : 'Radius X (rx)'}
        value={params.rx}
        min={5}
        max={100}
        step={0.5}
        onChange={(rx) => onChange({ rx })}
      />
      <Slider
        label={params.moduleType === MODULE_FONT ? 'Кегль ячейки (ry)' : 'Radius Y (ry)'}
        value={params.ry}
        min={2}
        max={40}
        step={0.5}
        onChange={(ry) => onChange({ ry })}
      />
      <Slider
        label="Stroke width"
        value={params.strokeWidth}
        min={0}
        max={6}
        step={0.1}
        onChange={(strokeWidth) => onChange({ strokeWidth })}
      />
      <Slider
        label="Fill opacity"
        value={params.fillOpacity}
        min={0}
        max={1}
        step={0.05}
        onChange={(fillOpacity) => onChange({ fillOpacity })}
      />

      {params.moduleType === MODULE_CUSTOM_SVG ? (
        <CustomSvgUpload params={params} onChange={onChange} />
      ) : null}

      {params.moduleType === MODULE_FONT ? (
        <FontModuleControls
          params={params}
          onChange={onChange}
          fontLoading={fontLoading}
          fontError={fontError}
        />
      ) : null}

      <div className="border-t border-studio-border pt-3">
        <Slider
          label="Module Angle"
          value={params.moduleAngle}
          min={-90}
          max={90}
          step={1}
          suffix="°"
          onChange={(moduleAngle) => onChange({ moduleAngle })}
        />
        <div className="mt-2 grid grid-cols-4 gap-1">
          {MODULE_ANGLE_PRESETS.map((angle) => (
            <Button
              key={angle}
              compact
              variant={params.moduleAngle === angle ? 'primary' : 'default'}
              onClick={() => onChange({ moduleAngle: angle })}
            >
              {angle}°
            </Button>
          ))}
        </div>
        <p className="mt-2 text-[10px] leading-snug text-studio-faint">
          Вращение вокруг локального центра каждого модуля. Габариты холста
          пересчитываются автоматически.
        </p>
      </div>
    </Accordion>
  );
}

function CustomSvgUpload({
  params,
  onChange,
}: {
  params: StyleParams;
  onChange: (patch: Partial<StyleParams>) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) {
        return;
      }
      try {
        const text = await file.text();
        const shape = parseCustomSvg(text);
        onChange({ customSvgMarkup: serializeStamp(shape), customSvgName: file.name });
        setError(null);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : 'Не удалось разобрать SVG');
      } finally {
        event.target.value = '';
      }
    },
    [onChange],
  );

  return (
    <div className="border-t border-studio-border pt-3">
      <FieldLabel>Файл модуля</FieldLabel>
      <input
        ref={inputRef}
        type="file"
        accept=".svg,image/svg+xml"
        onChange={handleFile}
        className="hidden"
      />
      <div className="flex gap-1">
        <Button fullWidth compact onClick={() => inputRef.current?.click()}>
          Загрузить SVG
        </Button>
        {params.customSvgMarkup ? (
          <Button
            compact
            variant="ghost"
            title="Убрать SVG и вернуться к овалу"
            onClick={() => onChange({ customSvgMarkup: '', customSvgName: '' })}
          >
            Сбросить
          </Button>
        ) : null}
      </div>
      <p className="mt-1.5 font-mono text-[10px] break-all text-studio-faint">
        {params.customSvgName || 'не загружен — рисуется овал'}
      </p>
      {error ? <p className="mt-1 text-[10px] text-[#ff5a52]">{error}</p> : null}
      <p className="mt-1 text-[10px] leading-snug text-studio-faint">
        Габариты штампа задаются ползунками rx и ry выше — масштабирование
        пропорциональное.
      </p>
    </div>
  );
}

function FontModuleControls({ params, onChange, fontLoading, fontError }: StyleSectionProps) {
  const weights = weightsForSubfamily(params.moduleFontSubfamily);

  const handleSubfamily = useCallback(
    (moduleFontSubfamily: string) => {
      const available = weightsForSubfamily(moduleFontSubfamily);
      const weight = available.includes(params.moduleFontWeight)
        ? params.moduleFontWeight
        : (available[0] ?? 'Regular');
      onChange({ moduleFontSubfamily, moduleFontWeight: weight });
    },
    [onChange, params.moduleFontWeight],
  );

  return (
    <div className="flex flex-col gap-3 border-t border-studio-border pt-3">
      <Select
        label="Семейство"
        value={params.moduleFontSubfamily}
        options={MODULE_FONT_SUBFAMILIES}
        onChange={handleSubfamily}
      />
      <Select
        label="Начертание"
        value={params.moduleFontWeight}
        options={weights.length > 0 ? weights : ['Regular']}
        onChange={(moduleFontWeight) => onChange({ moduleFontWeight })}
      />
      <TextField
        label="Строка символов"
        value={params.moduleFontChars}
        placeholder="например 01 или *#@!"
        onChange={(moduleFontChars) => onChange({ moduleFontChars })}
      />
      <p className="-mt-1.5 text-[10px] leading-snug text-studio-faint">
        Пустое поле — весь читаемый алфавит шрифта без служебных глифов.
      </p>
      <RadioGroup<FillOrder>
        label="Порядок заполнения"
        value={params.moduleFontFillOrder}
        options={FILL_ORDER_OPTIONS}
        onChange={(moduleFontFillOrder) => onChange({ moduleFontFillOrder })}
      />
      <Slider
        label="Символов в модуле"
        value={params.moduleFontSymbolsPerModule}
        min={1}
        max={4}
        step={1}
        onChange={(moduleFontSymbolsPerModule) => onChange({ moduleFontSymbolsPerModule })}
      />
      <Checkbox
        label="Рандом (Randomize)"
        checked={params.moduleFontRandomize}
        onChange={(moduleFontRandomize) => onChange({ moduleFontRandomize })}
      />
      <Slider
        label="Random Seed"
        value={params.seed}
        min={0}
        max={9999}
        step={1}
        onChange={(seed) => onChange({ seed })}
      />
      {fontLoading ? (
        <p className="text-[10px] text-studio-muted">Загрузка контуров шрифта…</p>
      ) : null}
      {fontError ? <p className="text-[10px] text-[#ff5a52]">{fontError}</p> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */

function SpacingSection({
  params,
  onChange,
}: {
  params: StyleParams;
  onChange: (patch: Partial<StyleParams>) => void;
}) {
  return (
    <Accordion title="Интервалы и плотность">
      <Slider
        label="Grid step X"
        value={params.stepX}
        min={2}
        max={60}
        step={0.5}
        onChange={(stepX) => onChange({ stepX })}
      />
      <Slider
        label="Grid step Y"
        value={params.stepY}
        min={1}
        max={40}
        step={0.5}
        onChange={(stepY) => onChange({ stepY })}
      />
      <p className="-mt-1 text-[10px] leading-snug text-studio-faint">
        Шаг меньше диаметра модуля даёт плотный нахлёст — это допустимо.
      </p>
      <Slider
        label="Matrix columns ×"
        value={params.colScale}
        min={1}
        max={3}
        step={1}
        onChange={(colScale) => onChange({ colScale })}
      />
      <Slider
        label="Matrix rows ×"
        value={params.rowScale}
        min={1}
        max={3}
        step={1}
        onChange={(rowScale) => onChange({ rowScale })}
      />
      <Slider
        label="Letter spacing"
        value={params.letterSpacing}
        min={0}
        max={6}
        step={0.5}
        onChange={(letterSpacing) => onChange({ letterSpacing })}
      />
    </Accordion>
  );
}

function DeformSection({
  params,
  onChange,
}: {
  params: StyleParams;
  onChange: (patch: Partial<StyleParams>) => void;
}) {
  return (
    <Accordion title="Деформации и FX">
      <Slider
        label="Slant / Skew Angle"
        value={params.slantAngle}
        min={-30}
        max={30}
        step={0.5}
        suffix="°"
        onChange={(slantAngle) => onChange({ slantAngle })}
      />
      <p className="-mt-1 text-[10px] leading-snug text-studio-faint">
        Наклон считается от Baseline: x += (y_baseline − y) · tan θ.
      </p>
      <Slider
        label="Glitch / Jitter X"
        value={params.jitterX}
        min={0}
        max={50}
        step={0.5}
        onChange={(jitterX) => onChange({ jitterX })}
      />
      <Slider
        label="Scanline Shift"
        value={params.rowJitter}
        min={0}
        max={50}
        step={0.5}
        onChange={(rowJitter) => onChange({ rowJitter })}
      />
      <Slider
        label="Random Seed"
        value={params.seed}
        min={0}
        max={9999}
        step={1}
        onChange={(seed) => onChange({ seed })}
      />
    </Accordion>
  );
}

function KerningSection({
  params,
  onChange,
}: {
  params: StyleParams;
  onChange: (patch: Partial<StyleParams>) => void;
}) {
  const [pair, setPair] = useState('');
  const [delta, setDelta] = useState(0);

  const entries = Object.entries(params.kerningPairs).sort(([a], [b]) =>
    a.localeCompare(b, 'ru'),
  );
  const normalizedPair = [...pair.toUpperCase()].slice(0, 2).join('');
  const canApply = [...normalizedPair].length === 2;

  const applyPair = useCallback(() => {
    if (!canApply) {
      return;
    }
    onChange({ kerningPairs: { ...params.kerningPairs, [normalizedPair]: delta } });
  }, [canApply, delta, normalizedPair, onChange, params.kerningPairs]);

  const removePair = useCallback(
    (key: string) => {
      const next = { ...params.kerningPairs };
      delete next[key];
      onChange({ kerningPairs: next });
    },
    [onChange, params.kerningPairs],
  );

  return (
    <Accordion title="Кернинг">
      <TextField
        label="Пара символов"
        value={pair}
        placeholder="например АУ"
        maxLength={2}
        onChange={setPair}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            applyPair();
          }
        }}
      />
      <Slider
        label="Сдвиг (колонки)"
        value={delta}
        min={-4}
        max={4}
        step={0.25}
        onChange={setDelta}
      />
      <Button fullWidth compact disabled={!canApply} onClick={applyPair}>
        Задать пару
      </Button>

      {entries.length === 0 ? (
        <p className="text-[10px] text-studio-faint">Пар пока нет.</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {entries.map(([key, value]) => (
            <li
              key={key}
              className="flex items-center justify-between gap-2 rounded border border-studio-border bg-studio-panel px-2 py-1"
            >
              <span className="font-mono text-[12px] text-studio-text">{key}</span>
              <span className="font-mono text-[11px] tabular-nums text-studio-muted">
                {value > 0 ? '+' : ''}
                {value}
              </span>
              <button
                type="button"
                onClick={() => removePair(key)}
                className="text-[10px] text-studio-faint transition-colors hover:text-[#ff5a52]"
                title={`Удалить пару ${key}`}
              >
                убрать
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="text-[10px] leading-snug text-studio-faint">
        Пары запекаются в экспортируемый шрифт как GPOS и таблица kern.
      </p>
    </Accordion>
  );
}

function ColorSection({
  params,
  onChange,
}: {
  params: StyleParams;
  onChange: (patch: Partial<StyleParams>) => void;
}) {
  return (
    <Accordion title="Цвет и направляющие">
      <ColorField label="Модули" value={params.fill} onChange={(fill) => onChange({ fill })} />
      <ColorField
        label="Контур модуля"
        value={params.stroke}
        onChange={(stroke) => onChange({ stroke })}
      />
      <ColorField
        label="Фон"
        value={params.background}
        onChange={(background) => onChange({ background })}
      />
      <ColorField
        label="Baseline и метрики"
        value={params.guideColor}
        onChange={(guideColor) => onChange({ guideColor })}
      />
      <ColorField
        label="Сетка"
        value={params.gridColor}
        onChange={(gridColor) => onChange({ gridColor })}
      />
      <div className="border-t border-studio-border pt-2">
        <Checkbox
          label="Фоновая сетка"
          checked={params.showGrid}
          onChange={(showGrid) => onChange({ showGrid })}
        />
        <Checkbox
          label="Baseline и Cap-Height"
          checked={params.showGuides}
          onChange={(showGuides) => onChange({ showGuides })}
        />
      </div>
    </Accordion>
  );
}
