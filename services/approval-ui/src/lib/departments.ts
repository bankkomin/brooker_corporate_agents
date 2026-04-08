import type { DepartmentConfig, Department } from "@/types/department";
import departmentsData from "@/config/departments.json";

const config = departmentsData as unknown as DepartmentConfig;

export function getDepartmentConfig(): DepartmentConfig {
  return config;
}

export function getDepartment(deptId: string): Department | undefined {
  return config.departments[deptId];
}

export function getDepartmentIds(): string[] {
  return Object.keys(config.departments);
}

export function getDepartmentColor(deptId: string): string {
  return config.departments[deptId]?.color ?? "#64748b";
}
