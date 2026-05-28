/**
 * Tipos partilhados entre as views da OverallPage (Q.115.L).
 */

export interface ScheduledOp {
  id: string;
  phase_id: string;
  phase_name: string;
  order_id?: string;
  product_id?: string;
  operator_id?: string;
  operator_name?: string;
  cliente?: string;
  start?: string;
  end?: string;
  duration_min?: number;
  status?: string;
}
