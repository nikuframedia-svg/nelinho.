import type { ReactNode } from 'react';
import { Modal } from '../dark/Modal';
import { DarkButton } from '../dark/DarkButton';
import { DarkInput, DarkTextarea } from '../dark/DarkInput';
import { DarkSelect } from '../dark/DarkSelect';

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

const FORM_ID = 'form-modal-body';

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

    fields.forEach((field) => {
      const value = formData.get(field.name);
      if (value !== null) {
        if (field.type === 'number') {
          data[field.name] = value === '' ? null : Number(value);
        } else if (field.type === 'checkbox') {
          const el = e.currentTarget.querySelector(`[name="${field.name}"]`) as HTMLInputElement | null;
          data[field.name] = el?.checked ?? false;
        } else {
          data[field.name] = value;
        }
      } else if (field.type === 'checkbox') {
        const el = e.currentTarget.querySelector(`[name="${field.name}"]`) as HTMLInputElement | null;
        data[field.name] = el?.checked ?? false;
      }
    });

    await onSubmit(data);
  };

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title={title}
      size="lg"
      footer={
        <>
          <DarkButton
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={isLoading}
          >
            {cancelLabel}
          </DarkButton>
          <DarkButton
            type="submit"
            form={FORM_ID}
            variant="primary"
            loading={isLoading}
            disabled={isLoading}
          >
            {submitLabel}
          </DarkButton>
        </>
      }
    >
      {description && (
        <p className="text-xs text-text-dark-tertiary mb-4">{description}</p>
      )}

      <form id={FORM_ID} onSubmit={handleSubmit} className="space-y-4">
        {fields.map((field) => {
          const initial = initialData[field.name];
          const labelNode = (
            <label className="block text-sm font-medium text-text-dark-secondary mb-1.5">
              {field.label}
              {field.required && <span className="text-danger ml-1" aria-hidden="true">*</span>}
            </label>
          );

          if (field.type === 'select') {
            return (
              <div key={field.name}>
                {labelNode}
                <DarkSelect
                  name={field.name}
                  required={field.required}
                  disabled={field.disabled}
                  defaultValue={initial ?? ''}
                  placeholder={field.placeholder ?? 'Selecione…'}
                  options={field.options ?? []}
                />
              </div>
            );
          }

          if (field.type === 'textarea') {
            return (
              <div key={field.name}>
                {labelNode}
                <DarkTextarea
                  name={field.name}
                  required={field.required}
                  disabled={field.disabled}
                  placeholder={field.placeholder}
                  defaultValue={initial ?? ''}
                  rows={4}
                />
              </div>
            );
          }

          if (field.type === 'checkbox') {
            return (
              <label
                key={field.name}
                className="flex items-center gap-2 text-sm text-text-dark-secondary cursor-pointer"
              >
                <input
                  type="checkbox"
                  name={field.name}
                  defaultChecked={Boolean(initial)}
                  disabled={field.disabled}
                  className="w-4 h-4 rounded border-bd-2 bg-dark-700 text-accent focus:ring-2 focus:ring-accent/30"
                />
                <span>{field.placeholder || field.label}</span>
              </label>
            );
          }

          return (
            <div key={field.name}>
              {labelNode}
              <DarkInput
                type={field.type || 'text'}
                name={field.name}
                required={field.required}
                disabled={field.disabled}
                placeholder={field.placeholder}
                defaultValue={initial ?? ''}
                min={field.min}
                max={field.max}
                step={field.step}
              />
            </div>
          );
        })}

        {children}
      </form>
    </Modal>
  );
}
