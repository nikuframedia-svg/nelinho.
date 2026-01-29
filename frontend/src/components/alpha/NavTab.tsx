import { cn } from '../../lib/utils';

interface NavTabProps {
  children: React.ReactNode;
  active?: boolean;
  onClick?: () => void;
}

export function NavTab({ children, active, onClick }: NavTabProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'alpha-nav-tab',
        active && 'active'
      )}
    >
      {children}
    </button>
  );
}







