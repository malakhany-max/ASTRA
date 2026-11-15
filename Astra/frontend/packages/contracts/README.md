# ASTRA TypeScript contracts

`domain.json` defines the UI view models. Run `npm run generate:types` from the
repository root to regenerate `src/types.ts` and to compile the shared wire
schemas in the read-only root `contracts/` folder into `src/wire/`.

Wire schema types are available under the `WireContracts` namespace, for
example `WireContracts.Reading` and `WireContracts.Status`. The generator reads
the shared files and writes only inside this package.
