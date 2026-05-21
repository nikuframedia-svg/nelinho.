/**
 * Q.68.4.D — Helpers tipados para o padrão "page lista CRUD" (BOMPage,
 * CustomersPage, EmployeesPage, ProductsPage, etc.).
 *
 * O frontend ainda não tem DTOs Pydantic-derived em todos os endpoints
 * (essa migração é Q.68.4.E via Orval). Estas aliases dão um vocabulário
 * comum sem reintroduzir `: any`.
 *
 * Convenções:
 *   - `MutationError`: catch handler do TanStack Query — sempre `Error`-shape
 *     com `.message` populado pelo client.ts (`apiFetch`).
 *   - `MutationPayload`: corpo de POST/PATCH/PUT — Pydantic recebe um dict;
 *     `Record<string, unknown>` é o equivalente TS sem desligar safety.
 *   - `EntityLite`: shape mínima usada em selects/maps (todas as entidades
 *     core têm `id`; outros campos são opcionais e cast-iterated).
 */

/** Erro propagado pelo TanStack Query onError. */
export type MutationError = Error & { message?: string };

/** Payload JSON-serializable para mutations. */
export type MutationPayload = Record<string, unknown>;

/** Shape mínima de uma entidade do core module (products, employees, etc.). */
export interface EntityLite {
  id: string;
  [key: string]: unknown;
}
