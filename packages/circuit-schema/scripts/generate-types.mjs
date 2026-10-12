import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { compile } from 'json-schema-to-typescript';

export const targets = [
  {
    name: 'CircuitDocument',
    schemaUrl: new URL('../schema/circuit.schema.json', import.meta.url),
    typesUrl: new URL('../src/circuit.ts', import.meta.url),
  },
  {
    name: 'ComponentCatalog',
    schemaUrl: new URL('../schema/catalog.schema.json', import.meta.url),
    typesUrl: new URL('../src/catalog.ts', import.meta.url),
  },
];

const banner = (schemaFile) => `/**
 * Ficheiro gerado a partir de schema/${schemaFile} — não editar à mão.
 * Regenerar com: pnpm --filter @vcccircuitlab/circuit-schema generate
 */`;

export async function generateTypes(target) {
  const schema = JSON.parse(await readFile(target.schemaUrl, 'utf8'));
  const schemaFile = fileURLToPath(target.schemaUrl).split(/[\\/]/).pop();
  return compile(schema, target.name, {
    bannerComment: banner(schemaFile),
    additionalProperties: false,
    unreachableDefinitions: true,
    style: { singleQuote: true },
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  for (const target of targets) {
    await writeFile(target.typesUrl, await generateTypes(target));
    console.log(`Tipos gerados em ${fileURLToPath(target.typesUrl)}`);
  }
}
