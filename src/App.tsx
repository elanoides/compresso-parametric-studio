import { Header } from './components/Layout/Header';
import { Sidebar } from './components/Layout/Sidebar';
import { GlyphInspector } from './components/Tabs/GlyphInspector';
import { PresetsGallery } from './components/Tabs/PresetsGallery';
import { WordTester } from './components/Tabs/WordTester';
import { useStudio } from './hooks/useStudio';

export default function App() {
  const studio = useStudio();

  return (
    <div className="flex h-full flex-col overflow-hidden bg-studio-bg">
      <Header
        activeTab={studio.tab}
        onTabChange={studio.setTab}
        activePreset={studio.activePreset}
        presetCount={Object.keys(studio.presets).length}
      />

      <div className="flex min-h-0 flex-1">
        <Sidebar
          params={studio.params}
          onChange={studio.updateParams}
          fontLoading={studio.fontLoading}
          fontError={studio.fontError}
          presets={studio.presets}
          activePreset={studio.activePreset}
          onApplyPreset={studio.applyPreset}
          onSavePreset={studio.saveActivePreset}
          onResetPreset={studio.resetToRegular}
          onCreatePreset={studio.createPreset}
        />

        <main className="min-w-0 flex-1 overflow-hidden p-4">
          {/* Only the active tab is mounted, so a 100-card gallery never
              competes with the render loop while sliders are moving. */}
          {studio.tab === 'word' ? (
            <WordTester
              context={studio.context}
              activePreset={studio.activePreset}
              text={studio.wordText}
              onTextChange={studio.setWordText}
              previewScale={studio.previewScale}
              onPreviewScaleChange={studio.setPreviewScale}
            />
          ) : null}

          {studio.tab === 'glyph' ? (
            <GlyphInspector
              context={studio.context}
              activePreset={studio.activePreset}
              char={studio.inspectChar}
              onCharChange={studio.setInspectChar}
            />
          ) : null}

          {studio.tab === 'styles' ? (
            <PresetsGallery
              presets={studio.presets}
              activePreset={studio.activePreset}
              specimen={studio.wordText}
              context={studio.context}
              onApply={studio.applyPreset}
              onSave={studio.saveActivePreset}
              onCreate={studio.createPreset}
              onCreateDefault={studio.createDefaultPreset}
              onDelete={studio.deletePreset}
              onReset={studio.resetToRegular}
              onImport={studio.replaceLibrary}
            />
          ) : null}
        </main>
      </div>
    </div>
  );
}
