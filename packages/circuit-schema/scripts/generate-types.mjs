import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { compile } from 'json-schema-to-typescript';

const schemaUrl = new URL('../schema/circuit.schema.json', import.meta.url);
export const typesUrl = new URL('../src/circuit.ts', import.meta.url);

const BANNER = `/**
 * Ficheiro gerado a partir de schema/circuit.schema.json — não editar à mão.
 * Regenerar com: pnpm --filter @vcccircuitlab/circuit-schema generate
 */`;

export async function generateTypes() {
  const schema = JSON.parse(await readFile(schemaUrl, 'utf8'));
  return compile(schema, 'CircuitDocument', {
    bannerComment: BANNER,
    additionalProperties: false,
    unreachableDefinitions: true,
    style: { singleQuote: true },
  });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await writeFile(typesUrl, await generateTypes());
  console.log(`Tipos gerados em ${fileURLToPath(typesUrl)}`);
}
