export type BreadcrumbItem = {
  label: string;
  url?: string;
};

export type StatusTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger';

export type EvidenceDetail = {
  label: string;
  value: string | number | null | undefined;
};
