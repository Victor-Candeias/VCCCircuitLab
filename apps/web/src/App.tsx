import { EditorCanvas } from './editor/EditorCanvas';

function App() {
  return (
    <div className="app">
      <header className="app__header">
        <h1>VCCCircuitLab</h1>
        <span className="app__subtitle">Editor de circuitos</span>
      </header>
      <main className="app__editor">
        <EditorCanvas />
      </main>
    </div>
  );
}

export default App;
