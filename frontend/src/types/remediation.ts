export interface RemediationStep {
  order: number;
  description: string;
  codeSnippet?: string;
  language?: string;
}

export interface RemediationGuide {
  id: string;
  title: string;
  explanation: string;
  severity: "critical" | "warning" | "info";
  steps: RemediationStep[];
}

export const REMEDIATION_GUIDES: Record<string, RemediationGuide> = {} as const;
