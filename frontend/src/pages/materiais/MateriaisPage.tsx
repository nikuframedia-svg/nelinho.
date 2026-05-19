/**
 * MateriaisPage — Materiais (shell · Q.60.V).
 *
 * As 4 tabs (Stock/Prospeção/Entregas/Fornecedores) foram decompostas para
 * ./tabs/. Primitivas partilhadas em ./materiaisShared.
 */
import { useState, type ReactNode } from 'react';
import { Boxes, Building2, Target, Truck } from 'lucide-react';
import { DarkPageLayout } from '../../layouts/DarkPageLayout';
import { Segmented } from '../../components/dark/Segmented';
import { StockTab } from './tabs/StockTab';
import { ProspecaoTab } from './tabs/ProspecaoTab';
import { EntregasTab } from './tabs/EntregasTab';
import { FornecedoresTab } from './tabs/FornecedoresTab';

type TabId = 'stock' | 'prospecao' | 'entregas' | 'fornecedores';

const TABS: Array<{ value: TabId; label: string; icon: ReactNode }> = [
  { value: 'stock', label: 'Catálogo', icon: <Boxes size={13} /> },
  { value: 'prospecao', label: 'Prospeção', icon: <Target size={13} /> },
  { value: 'entregas', label: 'Entregas', icon: <Truck size={13} /> },
  { value: 'fornecedores', label: 'Fornecedores', icon: <Building2 size={13} /> },
];

// ═══════════════════════════════════════════════════════════════════════════
// PAGE
// ═══════════════════════════════════════════════════════════════════════════

export default function MateriaisPage(): ReactNode {
  const [tab, setTab] = useState<TabId>('stock');

  return (
    <DarkPageLayout
      title="Materiais"
      subtitle="Stock, prospeção MRP, entregas, fornecedores"
      icon={<Boxes size={18} />}
    >
      <div style={{ marginBottom: 16 }}>
        <Segmented options={TABS} value={tab} onChange={setTab} />
      </div>

      {tab === 'stock' && <StockTab />}
      {tab === 'prospecao' && <ProspecaoTab />}
      {tab === 'entregas' && <EntregasTab />}
      {tab === 'fornecedores' && <FornecedoresTab />}
    </DarkPageLayout>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB · CATÁLOGO  (materiais derivados da BOM)
// ═══════════════════════════════════════════════════════════════════════════
