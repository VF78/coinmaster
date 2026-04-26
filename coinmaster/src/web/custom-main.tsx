import React from 'react';
import { createRoot } from 'react-dom/client';
import { CustomApp } from './CustomApp';
import { DialogProvider } from './components/DialogProvider';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <DialogProvider>
      <CustomApp />
    </DialogProvider>
  </React.StrictMode>
);
