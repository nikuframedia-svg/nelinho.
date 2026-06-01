// Dashboard
export { Dashboard } from './Dashboard';

// CORE Module
export { ProductsPage } from './core/ProductsPage';
export { MachinesPage } from './core/MachinesPage';
export { EmployeesPage } from './core/EmployeesPage';
export { OperationsPage } from './core/OperationsPage';
export { RatesPage } from './core/RatesPage';
export { TenantsPage } from './core/TenantsPage';
export { BOMPage } from './core/BOMPage';
export { CustomersPage } from './core/CustomersPage';
export { SuppliersPage } from './core/SuppliersPage';

// PLAN Module
// Planeamento vive em pages/overall/OverallPage.tsx (rota /overall). A antiga
// SchedulingPage (Q.53.G) e a PlaneamentoPage (Q.153.D3) foram removidas —
// /overall absorveu replanear/aprovar + drag-drop + preview.
export { MRPPage } from './plan/MRPPage';
export { CapacityPage } from './plan/CapacityPage';

// DISPATCH Module — Sprint Q.2
export { default as DispatchPage } from './dispatch/DispatchPage';

// PROFIT Module
export { COGSPage } from './profit/COGSPage';
export { PricingPage } from './profit/PricingPage';
export { ScenariosPage } from './profit/ScenariosPage';
export { OEEPage } from './profit/OEEPage';
export { QualityPage } from './profit/QualityPage';
export { KPIsPage } from './profit/KPIsPage';

// HR Module
export { AllocationsPage } from './hr/AllocationsPage';
export { PayrollPage } from './hr/PayrollPage';
export { ProductivityPage } from './hr/ProductivityPage';

// WORKFORCE Module - Decision OS for workforce management
export { WorkforceDashboard } from './workforce';

// SUPPLY Module
export { InventoryPage } from './supply/InventoryPage';
export { ForecastPage } from './supply/ForecastPage';
export { ROPPage } from './supply/ROPPage';
export { ABCPage } from './supply/ABCPage';

// SHARED Module - Decision Intelligence Platform
export { DecisionsPage } from './shared/DecisionsPage';
