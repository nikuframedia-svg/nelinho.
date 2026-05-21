// EmployeesPage — tipo Employee partilhado (Q.60.W).

export interface Employee {
  id: string;
  name: string;
  employee_code?: string;
  status: string;
  skills: string[];
  skillIds: string[];
  department: string;
  shift_pattern?: string;
}
