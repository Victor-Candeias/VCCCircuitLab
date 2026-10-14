import { useState } from 'react';
import { RegisterDialog } from './auth/RegisterDialog';
import { EditorCanvas } from './editor/EditorCanvas';
import { ProjectMenu } from './project/ProjectMenu';
import './auth/auth.css';

function App() {
  const [showRegister, setShowRegister] = useState(false);
  return (
    <div className="app">
      <header className="app__header">
        <h1>VCCCircuitLab</h1>
        <span className="app__subtitle">Editor de circuitos</span>
        <ProjectMenu />
        <button type="button" className="app__account" onClick={() => setShowRegister(true)}>
          Criar conta
        </button>
      </header>
      <main className="app__editor">
        <EditorCanvas />
      </main>
      {showRegister && <RegisterDialog onClose={() => setShowRegister(false)} />}
    </div>
  );
}

export default App;
