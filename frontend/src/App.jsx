import { Routes, Route } from "react-router-dom";
import useJob from "./hooks/useJob";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import InputPage from "./pages/InputPage";
import ProcessingPage from "./pages/ProcessingPage";
import ResultPage from "./pages/ResultPage";

export default function App() {
  const job = useJob();

  return (
    <>
      <Navbar />
      <Routes>
        <Route
          path="/"
          element={
            <InputPage
              prompt={job.prompt}
              setPrompt={job.setPrompt}
              options={job.options}
              updateOption={job.updateOption}
              onGenerate={job.handleGenerate}
            />
          }
        />
        <Route
          path="/job/:job_id"
          element={
            <ProcessingPage
              status={job.status}
              progress={job.progress}
              previewUrls={job.previewUrls}
              error={job.error}
              jobId={job.jobId}
              resumeJob={job.resumeJob}
              handleRetry={job.handleRetry}
            />
          }
        />
        <Route
          path="/job/:job_id/result"
          element={
            <ResultPage
              status={job.status}
              jobId={job.jobId}
              previewUrls={job.previewUrls}
              handleReset={job.handleReset}
              resumeJob={job.resumeJob}
            />
          }
        />
      </Routes>
      <Footer />
    </>
  );
}