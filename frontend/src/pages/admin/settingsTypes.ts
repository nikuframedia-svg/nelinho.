// SettingsPage — tipos partilhados (Q.60.R).

export interface ConfigKeyRow {
  key: string;
  label: string;
  hint: string;
  dataType: 'int' | 'float' | 'bool' | 'string';
}
