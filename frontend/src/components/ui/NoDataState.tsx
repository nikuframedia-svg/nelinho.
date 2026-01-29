import { Database } from 'lucide-react';

interface NoDataStateProps {
  title: string;
  message: string;
  icon?: React.ReactNode;
}

export function NoDataState({ title, message, icon }: NoDataStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-8">
      <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mb-4">
        {icon || <Database size={32} className="text-slate-300" />}
      </div>
      <h3 className="text-lg font-semibold text-slate-600 mb-2">{title}</h3>
      <p className="text-sm text-slate-400 text-center max-w-md">{message}</p>
    </div>
  );
}










