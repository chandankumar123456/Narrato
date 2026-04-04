import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import useEditor from "../hooks/useEditor";
import EditorNavbar from "../components/editor/EditorNavbar";
import SlidePanel from "../components/editor/SlidePanel";
import SlideCanvas from "../components/editor/SlideCanvas";
import ControlPanel from "../components/editor/ControlPanel";
import AIAssistant from "../components/editor/AIAssistant";
import ExportModal from "../components/editor/ExportModal";
import EditModal from "../components/editor/EditModal";

/**
 * Interactive editor page — full-screen slide editor with
 * sidebar, canvas, controls, AI assist, and export.
 */
export default function EditorPage() {
  const { job_id } = useParams();
  const editor = useEditor(job_id);
  const [showAI, setShowAI] = useState(false);
  const [showExport, setShowExport] = useState(false);
  const [showEdit, setShowEdit] = useState(false);

  // Load slides on mount
  useEffect(() => {
    if (job_id) {
      editor.loadSlides();
    }
  }, [job_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const activeSlideData = editor.slides[editor.activeSlide] || null;

  // If no slides loaded and not loading, show loading state
  if (editor.loading && editor.slides.length === 0) {
    return (
      <div className="h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-white/40">Loading slides...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-[#0a0a0f] overflow-hidden">
      {/* Editor Navbar */}
      <EditorNavbar
        onExport={() => setShowExport(true)}
        jobId={job_id}
      />

      {/* Error Banner */}
      {editor.error && (
        <div className="px-4 py-2 bg-red-600/10 border-b border-red-600/20 flex items-center justify-between">
          <span className="text-xs text-red-300">{editor.error}</span>
          <button
            onClick={() => editor.setError(null)}
            className="text-xs text-red-300/60 hover:text-red-300 cursor-pointer border-0 bg-transparent"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main Editor Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar — Slide Panel */}
        <SlidePanel
          slides={editor.slides}
          activeSlide={editor.activeSlide}
          onSelect={editor.setActiveSlide}
          onDuplicate={editor.handleDuplicate}
          onDelete={editor.handleDelete}
          slideLoading={editor.slideLoading}
        />

        {/* Center — Slide Canvas */}
        <SlideCanvas
          slide={activeSlideData}
          slideIndex={editor.activeSlide}
          totalSlides={editor.slides.length}
          isLoading={editor.slideLoading === editor.activeSlide}
          onNavigate={editor.setActiveSlide}
          onRegenerate={() => {
            if (activeSlideData) {
              setShowAI(true);
            }
          }}
          onDuplicate={() => {
            if (activeSlideData) {
              editor.handleDuplicate(activeSlideData.slide_id);
            }
          }}
          onEdit={() => setShowEdit(true)}
        />

        {/* Right — Control Panel */}
        <ControlPanel
          slide={activeSlideData}
          theme={editor.theme}
          onRestyle={editor.handleRestyle}
          onOpenAI={() => setShowAI(true)}
          onOpenExport={() => setShowExport(true)}
          onEdit={() => setShowEdit(true)}
          loading={editor.loading}
        />
      </div>

      {/* AI Assistant Panel */}
      <AIAssistant
        isOpen={showAI}
        onClose={() => setShowAI(false)}
        slideId={activeSlideData?.slide_id}
        slideType={activeSlideData?.type}
        onRegenerate={editor.handleRegenerate}
        loading={editor.slideLoading !== null}
      />

      {/* Export Modal */}
      <ExportModal
        isOpen={showExport}
        onClose={() => setShowExport(false)}
        jobId={job_id}
        slideCount={editor.slides.length}
      />

      {/* Edit Modal */}
      <EditModal
        isOpen={showEdit}
        onClose={() => setShowEdit(false)}
        slide={activeSlideData}
        onSave={editor.handleUpdateSlide}
        loading={editor.slideLoading !== null}
      />
    </div>
  );
}
