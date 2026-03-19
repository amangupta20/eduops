import { Navigate, Route, Routes } from 'react-router-dom'

import { Toaster } from "@/components/ui/toaster";
import ScenarioCatalogue from "@/pages/ScenarioCatalogue";
import ScenarioWorkspace from "./pages/ScenarioWorkspace";

function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<ScenarioCatalogue />} />
        <Route path="/workspace/:id" element={<ScenarioWorkspace />} />
        <Route path="/session/:id" element={<ScenarioWorkspace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toaster />
    </>
  );
}

export default App;
