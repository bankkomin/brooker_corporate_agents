export interface DataAccess {
  qdrantCollections: string[];
  mirrorPaths: string[];
  excelFiles: string[];
  sensitivityLevel: "public" | "internal" | "confidential" | "restricted";
  vaultPath?: string;
  wikiCollection?: string;
}

export interface Escalation {
  canEscalateTo: string[];
  hodEmails: string[];
}

export interface Department {
  name: string;
  shortName: string;
  description: string;
  color: string;
  icon: string;
  agents: string[];
  dataAccess: DataAccess;
  escalation: Escalation;
  dashboardWidgets: string[];
  slackChannels: Record<string, string>;
}

export interface DepartmentConfig {
  version: string;
  departments: Record<string, Department>;
  globalAccess: {
    sharedCollections: string[];
    roles: Record<string, { canRead: string[]; canApprove: string[] }>;
  };
}
