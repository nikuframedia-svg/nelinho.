/**
 * ToolRegistryPage — Admin page for LLM Tool Registry
 */

import { ModuleErrorBoundary, ToolRegistryPage as ToolRegistryContent } from '@/components/palantir';

export function ToolRegistryPage() {
  return (
    <ModuleErrorBoundary moduleName="ToolRegistry">
      <div className="p-6">
        <ToolRegistryContent />
      </div>
    </ModuleErrorBoundary>
  );
}

export default ToolRegistryPage;

