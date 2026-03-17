import { Navigate, Route, Routes } from 'react-router-dom'

import { Toaster } from "@/components/ui/toaster";
import Home from './pages/Home'
import Session from './pages/Session'

function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/session/:id" element={<Session />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toaster />
    </>
  );
}

export default App;
