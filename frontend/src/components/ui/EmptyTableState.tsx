import { Search, FileX } from 'lucide-react';

interface EmptyTableStateProps {
  title?: string;
  message?: string;
  icon?: React.ReactNode;
  isSearchResult?: boolean;
}

export function EmptyTableState({ 
  title = 'Sem resultados', 
  message = 'Não foram encontrados registos com os filtros aplicados.',
  icon,
  isSearchResult = true 
}: EmptyTableStateProps) {
  return (
    <tr>
      <td colSpan={100} className="py-12">
        <div className="flex flex-col items-center justify-center text-center">
          <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center mb-3">
            {icon || (isSearchResult ? (
              <Search size={24} className="text-slate-300" />
            ) : (
              <FileX size={24} className="text-slate-300" />
            ))}
          </div>
          <h3 className="text-sm font-semibold text-slate-600 mb-1">{title}</h3>
          <p className="text-xs text-slate-400 max-w-xs">{message}</p>
        </div>
      </td>
    </tr>
  );
}

// For use outside of tables (grid layouts, etc.)
export function EmptyListState({ 
  title = 'Sem resultados', 
  message = 'Não foram encontrados registos com os filtros aplicados.',
  icon,
  isSearchResult = true 
}: EmptyTableStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center mb-3">
        {icon || (isSearchResult ? (
          <Search size={24} className="text-slate-300" />
        ) : (
          <FileX size={24} className="text-slate-300" />
        ))}
      </div>
      <h3 className="text-sm font-semibold text-slate-600 mb-1">{title}</h3>
      <p className="text-xs text-slate-400 max-w-xs">{message}</p>
    </div>
  );
}










