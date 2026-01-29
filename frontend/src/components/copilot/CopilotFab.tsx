import { useState, useEffect } from 'react';
import { CopilotDrawer } from './CopilotDrawer';
import copilotMascotImage from '../../assets/copilot-mascot.png';

export function CopilotFab() {
  const [isOpen, setIsOpen] = useState(false);
  const [initialQuery, setInitialQuery] = useState<string | null>(null);
  const [showTooltip, setShowTooltip] = useState(false);
  const [openedViaFab, setOpenedViaFab] = useState(false);
  const [buttonSize, setButtonSize] = useState({ width: '100px', height: '100px' });
  
  // Responsive button size
  useEffect(() => {
    const updateSize = () => {
      if (window.innerWidth >= 640) {
        setButtonSize({ width: '140px', height: '140px' });
      } else {
        setButtonSize({ width: '100px', height: '100px' });
      }
    };
    
    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, []);
  
  // Escutar evento para abrir drawer com query pré-formatada
  useEffect(() => {
    const handleOpenEvent = (event: CustomEvent) => {
      setInitialQuery(event.detail.query);
      setOpenedViaFab(false); // Não é via FAB, é via outro componente
      setIsOpen(true);
    };
    
    window.addEventListener('copilot:open', handleOpenEvent as EventListener);
    return () => {
      window.removeEventListener('copilot:open', handleOpenEvent as EventListener);
    };
  }, []);

  const handleClose = () => {
    setIsOpen(false);
    setInitialQuery(null);
    setOpenedViaFab(false);
  };

  const handleClick = () => {
    setOpenedViaFab(true); // Marcar que foi aberto via FAB
    setIsOpen(true);
  };

  return (
    <>
      {/* Tooltip - apenas no desktop (hover) e quando chat não está aberto */}
      {showTooltip && !isOpen && (
        <div className="hidden sm:block fixed bottom-32 right-6 z-[99] animate-in fade-in slide-in-from-bottom-2 duration-200">
          <div className="glass-card-strong px-4 py-3 max-w-[200px] relative shadow-glow-teal">
            <p className="text-base font-bold text-white mb-1 drop-shadow-lg">
              Olá! Sou o Nelinho 👋
            </p>
            <p className="text-sm text-slate-200 font-medium">
              Em que posso ajudar?
            </p>
            {/* Seta apontando para o robô */}
            <div className="absolute bottom-0 right-4 transform translate-y-full">
              <div className="w-0 h-0 border-l-8 border-r-8 border-t-8 border-transparent border-t-dark-700"></div>
            </div>
          </div>
        </div>
      )}

      {/* Floating Action Button - APENAS O ROBÔ (sem bolinha) - visível mesmo quando chat está aberto, mas abaixo do input */}
      <button
        onClick={handleClick}
        onMouseEnter={() => !isOpen && setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className="fixed bottom-6 right-6 bg-transparent border-0 p-0 cursor-pointer group z-[150] pointer-events-auto"
          style={{
            width: buttonSize.width,
            height: buttonSize.height,
            minWidth: '64px',
            minHeight: '64px',
            transform: showTooltip ? 'translateY(-2px) scale(1.03)' : 'translateY(0) scale(1)',
            transition: 'transform 200ms ease-out',
          }}
          aria-label="Abrir Nelinho"
        >
          {/* Container do robô - sem background, sem círculo */}
          <div className="relative w-full h-full flex items-center justify-center">
            {/* Glow premium no hover - múltiplas camadas de drop-shadow */}
            <img
              src={copilotMascotImage}
              alt="Nelinho - Abrir chat"
              className="w-full h-full object-contain select-none"
              style={{ 
                filter: showTooltip 
                  ? 'drop-shadow(0 0 8px rgba(255, 255, 255, 0.8)) drop-shadow(0 0 16px rgba(147, 197, 253, 0.6)) drop-shadow(0 0 24px rgba(59, 130, 246, 0.4)) drop-shadow(0 4px 12px rgba(255, 107, 107, 0.3))'
                  : 'none',
                transition: 'filter 200ms ease-out',
                pointerEvents: 'none',
              }}
              draggable={false}
            />
            
            {/* Glow radial gradient sutil (opcional, para efeito extra) */}
            {showTooltip && (
              <div 
                className="absolute inset-0 pointer-events-none"
                style={{
                  background: 'radial-gradient(circle at center, rgba(147, 197, 253, 0.15) 0%, transparent 70%)',
                  filter: 'blur(8px)',
                  zIndex: -1,
                }}
              />
            )}
          </div>
        </button>
      
      {/* Drawer */}
      {isOpen && (
        <CopilotDrawer 
          isOpen={isOpen} 
          onClose={handleClose} 
          initialQuery={initialQuery}
          openedViaFab={openedViaFab}
        />
      )}
    </>
  );
}
