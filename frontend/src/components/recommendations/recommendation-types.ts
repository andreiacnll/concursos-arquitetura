export type RecommendationCard = {
  competition_id: number;
  title: string;
  entity?: string;
  location?: string;
  link?: string;
  published_at?: string;
  deadline?: string;
  base_price?: string;
  procedure_type?: string;
  award_criteria_type?: string;
  award_criteria_summary?: string;
  status?: string;
  compatibility_score?: number | null;
  compatibility_label?: string;
  score_breakdown?: {
    label: string;
    impact: string;
    value?: number | null;
  }[];
  summary: string;
  strengths: string[];
  attention_points: string[];
  missing_information: string[];
  action_label: string;
};

export type RecommendationListResponse = RecommendationCard[];
