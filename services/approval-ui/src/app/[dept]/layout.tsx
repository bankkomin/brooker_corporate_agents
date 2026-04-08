import { redirect } from "next/navigation";
import { getDepartmentIds } from "@/lib/departments";
import { DepartmentShell } from "@/components/shell/department-shell";

export default async function DepartmentLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ dept: string }>;
}) {
  const { dept } = await params;

  // Validate department exists in config
  const validDepts = getDepartmentIds();
  if (!validDepts.includes(dept)) {
    redirect("/");
  }

  return <DepartmentShell dept={dept}>{children}</DepartmentShell>;
}
