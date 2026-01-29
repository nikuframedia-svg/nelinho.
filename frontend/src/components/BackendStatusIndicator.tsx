import { useState, useEffect } from 'react';
import { Wifi, WifiOff, Loader2 } from 'lucide-react';
import { Badge } from './ui/Badge';
import { getBackendStatus, onBackendStatusChange, checkBackendHealth } from '../lib/backend-health';

export function BackendStatusIndicator() {
  const [status, setStatus] = useState<ReturnType<typeof getBackendStatus>>(getBackendStatus());

  useEffect(() => {
    // Subscribe to status changes
    const unsubscribe = onBackendStatusChange(setStatus);
    
    // Cleanup on unmount
    return unsubscribe;
  }, []);

  const handleRetry = () => {
    checkBackendHealth();
  };

  if (status === 'checking') {
    return (
      <Badge variant="neutral" className="flex items-center gap-1.5 px-2.5 py-1">
        <Loader2 size={12} className="animate-spin" />
        <span className="text-xs">Verificando...</span>
      </Badge>
    );
  }

  if (status === 'online') {
    return (
      <Badge variant="success" className="flex items-center gap-1.5 px-2.5 py-1">
        <Wifi size={12} />
        <span className="text-xs">Backend Online</span>
      </Badge>
    );
  }

  // status === 'offline'
  return (
    <button 
      onClick={handleRetry}
      title="Clicar para verificar novamente"
      className="cursor-pointer hover:opacity-80 transition-opacity"
    >
      <Badge 
        variant="danger" 
        className="flex items-center gap-1.5 px-2.5 py-1" 
      >
        <WifiOff size={12} />
        <span className="text-xs">Backend Offline</span>
      </Badge>
    </button>
  );
}





