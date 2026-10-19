import '@testing-library/jest-dom/vitest';
import 'fake-indexeddb/auto';
import { cleanup } from '@testing-library/react';
import type { ComponentCatalog } from '@vcccircuitlab/circuit-schema';
import catalogFixture from '@vcccircuitlab/circuit-schema/fixtures/catalog.json';
import { afterEach } from 'vitest';
import { setCatalog } from '../editor/catalog';
import { mockReactFlow } from './reactFlowMocks';

mockReactFlow();
// Em produção o catálogo vem de `GET /api/v1/components` (F2-11); nos testes usa-se a fixture.
setCatalog(catalogFixture as ComponentCatalog);

afterEach(() => {
  cleanup();
});
