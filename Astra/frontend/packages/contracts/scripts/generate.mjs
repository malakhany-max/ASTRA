import { mkdir, readdir, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { compileFromFile } from 'json-schema-to-typescript'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '../..', '..')
const packageRoot = path.resolve(here, '..')
const wireRoot = path.join(root, '..', 'backend', 'contracts')

const source = path.join(packageRoot, 'domain.json')
const target = path.join(packageRoot, 'src/types.ts')

const ts = await compileFromFile(source, {
  cwd: packageRoot,
  bannerComment: [
    '/* eslint-disable */',
    '/**',
    ' * Generated from contracts/domain.json by `npm run generate:types`.',
    ' * Do not edit by hand - update the JSON schema and regenerate.',
    ' */',
  ].join('\n'),
  style: { singleQuote: true, semi: false, printWidth: 100 },
})

await writeFile(target, ts, 'utf8')
console.log(`generated ${path.relative(root, target)}`)

// Keep the UI view models above, and also expose types compiled directly from
// the shared wire schemas. The shared contracts folder is read-only; generated
// output lives inside this package.
const wireOutput = path.join(packageRoot, 'src', 'wire')
await mkdir(wireOutput, { recursive: true })
const schemaFiles = (await readdir(wireRoot))
  .filter((file) => file.endsWith('.schema.json'))
  .sort()

if (schemaFiles.length === 0) {
  throw new Error(`No shared JSON schemas found in ${wireRoot}`)
}

const exports = []
for (const file of schemaFiles) {
  const name = file.replace('.schema.json', '')
  const output = path.join(wireOutput, `${name}.ts`)
  const generated = await compileFromFile(path.join(wireRoot, file), {
    cwd: wireRoot,
    bannerComment: `/** Generated from contracts/${file}; do not edit by hand. */`,
    style: { singleQuote: true, semi: false, printWidth: 100 },
  })
  await writeFile(output, generated, 'utf8')
  const namespace = name.replace(/(?:^|[-_])([a-z])/g, (_, letter) => letter.toUpperCase())
  exports.push(`export * as ${namespace} from './wire/${name}'`)
  console.log(`generated ${path.relative(root, output)}`)
}

await writeFile(path.join(packageRoot, 'src', 'canonical.ts'), `${exports.join('\n')}\n`, 'utf8')
