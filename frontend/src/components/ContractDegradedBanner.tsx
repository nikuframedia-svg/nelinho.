import { useState, useEffect } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import { getApiBase } from '../lib/api';

// Q.21.A — porta única via api.ts (concorda com VITE_API_URL).
const API_BASE = getApiBase();
const EXPECTED_CONTRACT_VERSION = '1.0.0';

export function ContractDegradedBanner() {
  const [show, setShow] = useState(false);
  const [serverVersion, setServerVersion] = useState<string | null>(null);

  useEffect(() => {
    const checkContractVersion = async () => {
      try {
        const response = await fetch(`${API_BASE}/health`, {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' },
        });
        
        const contractVersion = response.headers.get('X-Api-Contract');
        
        if (contractVersion && contractVersion !== EXPECTED_CONTRACT_VERSION) {
          setServerVersion(contractVersion);
          setShow(true);
        }
      } catch {
        // Silently ignore - banner is for contract mismatch, not connection errors
      }
    };

    checkContractVersion();
  }, []);

  if (!show) return null;

  return (
    <div className="bg-amber-50 border-b border-amber-200 px-4 py-2">
      <div className="max-w-[1600px] mx-auto flex items-center justify-between">
        <div className="flex items-center gap-3">
          <AlertTriangle size={18} className="text-amber-600" />
          <p className="text-sm text-amber-800">
            <strong>API Contract Mismatch:</strong> Frontend expects v{EXPECTED_CONTRACT_VERSION} but server reports v{serverVersion}. Some features may not work correctly.
          </p>
        </div>
        <button 
          onClick={() => setShow(false)}
          className="p-1 hover:bg-amber-100 rounded transition-colors"
        >
          <X size={16} className="text-amber-600" />
        </button>
      </div>
    </div>
  );
}





