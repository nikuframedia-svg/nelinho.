import type { ReactNode } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogCloseButton } from './Dialog';
import { Button } from './Button';

export interface FormField {
  name: string;
  label: string;
  type?: 'text' | 'number' | 'email' | 'tel' | 'date' | 'select' | 'textarea' | 'checkbox';
  placeholder?: string;
  required?: boolean;
  options?: { value: string; label: string }[];
  min?: number;
  max?: number;
  step?: number;
  defaultValue?: string | number | boolean;
  disabled?: boolean;
}

interface FormModalProps {
  title: string;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: Record<string, any>) => void | Promise<void>;
  initialData?: Record<string, any>;
  fields: FormField[];
  isLoading?: boolean;
  submitLabel?: string;
  cancelLabel?: string;
  description?: string;
  children?: ReactNode;
}

export function FormModal({
  title,
  isOpen,
  onClose,
  onSubmit,
  initialData = {},
  fields,
  isLoading = false,
  submitLabel = 'Guardar',
  cancelLabel = 'Cancelar',
  description,
  children,
}: FormModalProps) {
  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const data: Record<string, any> = {};
    
    fields.forEach(field => {
      const value = formData.get(field.name);
      if (value !== null) {
        if (field.type === 'number') {
          data[field.name] = value === '' ? null : Number(value);
        } else if (field.type === 'checkbox') {
          data[field.name] = (e.currentTarget.querySelector(`[name="${field.name}"]`) as HTMLInputElement)?.checked || false;
        } else {
          data[field.name] = value;
        }
      }
    });
    
    await onSubmit(data);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl w-full">
        <DialogCloseButton onClose={onClose} />
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <p className="text-sm text-slate-500 mt-1">{description}</p>}
        </DialogHeader>
        
        <form onSubmit={handleSubmit} className="flex flex-col flex-1 overflow-hidden">
          <div className="px-6 py-4 flex-1 overflow-y-auto">
            <div className="space-y-4">
              {fields.map(field => (
                <div key={field.name}>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    {field.label}
                    {field.required && <span className="text-red-500 ml-1">*</span>}
                  </label>
                  
                  {field.type === 'select' ? (
                    <select
                      name={field.name}
                      required={field.required}
                      defaultValue={initialData[field.name] || ''}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">Selecione...</option>
                      {field.options?.map(option => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  ) : field.type === 'textarea' ? (
                    <textarea
                      name={field.name}
                      required={field.required}
                      placeholder={field.placeholder}
                      defaultValue={initialData[field.name] || ''}
                      rows={4}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  ) : field.type === 'checkbox' ? (
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        name={field.name}
                        defaultChecked={initialData[field.name] || false}
                        className="w-4 h-4 text-blue-600 border-slate-300 rounded focus:ring-blue-500"
                      />
                      <span className="text-sm text-slate-600">{field.placeholder || field.label}</span>
                    </label>
                  ) : (
                    <input
                      type={field.type || 'text'}
                      name={field.name}
                      required={field.required}
                      placeholder={field.placeholder}
                      defaultValue={initialData[field.name] || ''}
                      min={field.min}
                      max={field.max}
                      step={field.step}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  )}
                </div>
              ))}
              
              {children}
            </div>
          </div>
          
          <div className="px-6 py-4 border-t border-slate-200 flex justify-end gap-3">
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
              disabled={isLoading}
            >
              {cancelLabel}
            </Button>
            <Button
              type="submit"
              variant="primary"
              loading={isLoading}
              disabled={isLoading}
            >
              {submitLabel}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}




