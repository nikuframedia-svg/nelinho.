/**
 * Q.61.26 — orval config para gerar TypeScript hooks contra
 * /openapi.json do FastAPI.
 *
 * Como correr (manual):
 *
 *   1. Levanta o backend dev:
 *        $env:PYTHONPATH = "."
 *        .\.venv\Scripts\python.exe -m uvicorn src.main:app --reload --port 8001
 *
 *   2. Em outro shell:
 *        cd frontend
 *        npm run gen:api
 *
 *   3. Commitar o resultado em src/lib/api/generated/.
 *
 * Decisões:
 *   * `client: 'react-query'` — TanStack Query v5 hooks (alinhado com
 *     o que ja usamos em todo o frontend).
 *   * `mode: 'tags-split'` — um ficheiro por tag OpenAPI (governance/
 *     plan/quality/...). Cada tag fica isolada e import-friendly.
 *   * `mutator` aponta para `lib/api/client.ts:request` — usa o nosso
 *     apiFetch central (Q.61.07/Q.61.12: tenant + trace_id automaticos).
 *   * `target` em `src/lib/api/generated/` (gitignored por enquanto;
 *     decidir em Q.62 se vai a commit ou nao).
 *
 * NAO corrido nesta sessao — primeira geracao requer backend a correr.
 * Luis kick-off quando quiser.
 */
import { defineConfig } from 'orval';

export default defineConfig({
  nelinho: {
    input: {
      target: 'http://localhost:8001/openapi.json',
    },
    output: {
      target: './src/lib/api/generated/api.ts',
      schemas: './src/lib/api/generated/schemas',
      client: 'react-query',
      mode: 'tags-split',
      override: {
        mutator: {
          path: './src/lib/api/orvalMutator.ts',
          name: 'orvalRequest',
        },
        query: {
          useQuery: true,
          useMutation: true,
        },
      },
    },
  },
});
