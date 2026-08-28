# shared

Cross-cutting values used by both `extension` and `backend`.

- `constants.json` — plain JSON so it can be read from TypeScript (`import` with
  `resolveJsonModule`) and from Python (`json.load`) without extra tooling.
- `types.ts` — TypeScript shapes for data exchanged with the backend. The
  backend's Pydantic models should be kept in sync with these by hand for now;
  if the two drift enough to hurt, consider generating one from the other.

Nothing in this package has a build step — it's imported directly by source
path from both sides.
