import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';

// View Pages
import Dashboard from './pages/Dashboard';
import Monitoring from './pages/Monitoring';
import Profiling from './pages/Profiling';
import Classification from './pages/Classification';
import Congestion from './pages/Congestion';
import Policies from './pages/Policies';
import Control from './pages/Control';
import Traces from './pages/Traces';
import Explainability from './pages/Explainability';
import Explanations from './pages/Explanations';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Navbar />
        <div className="layout-body">
          <Sidebar />
          <main className="main-viewport">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/monitoring" element={<Monitoring />} />
              <Route path="/profiling" element={<Profiling />} />
              <Route path="/classification" element={<Classification />} />
              <Route path="/congestion" element={<Congestion />} />
              <Route path="/policies" element={<Policies />} />
              <Route path="/control" element={<Control />} />
              <Route path="/traces" element={<Traces />} />
              <Route path="/explainability" element={<Explainability />} />
              <Route path="/explanations" element={<Explanations />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}
