// Importação da imagem do mascote do COPILOT
import React from 'react';
import copilotMascotImage from '../../assets/copilot-mascot.png';
import { Bot } from 'lucide-react';

interface CopilotMascotProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

const sizeMap = {
  sm: 'h-14', // ~56px
  md: 'h-20', // ~80px
  lg: 'h-24', // ~96px
  xl: 'h-40', // ~160px
};

export function CopilotMascot({ size = 'md', className = '' }: CopilotMascotProps) {
  // Tentar carregar a imagem, se falhar mostrar placeholder
  const [imageError, setImageError] = React.useState(false);

  if (imageError) {
    // Placeholder caso a imagem não carregue
    const iconSize = size === 'sm' ? 28 : size === 'md' ? 40 : size === 'lg' ? 48 : 80;
    return (
      <div className={`${sizeMap[size]} w-auto flex items-center justify-center bg-slate-100 rounded-lg ${className}`}>
        <Bot size={iconSize} className="text-slate-400" />
      </div>
    );
  }

  return (
    <img
      src={copilotMascotImage}
      alt="Nelinho - Mascote do sistema"
      className={`${sizeMap[size]} w-auto object-contain ${className}`}
      style={{ opacity: 1 }}
      onError={() => setImageError(true)}
    />
  );
}
