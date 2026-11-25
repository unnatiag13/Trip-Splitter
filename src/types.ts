export type SplitMethod = 'equal' | 'custom' | 'percentage';
export type TripStatus = 'active' | 'completed';

export interface EmailProviderStatus {
  configured: boolean;
  mode: 'live' | 'demo';
  provider: 'resend' | 'smtp' | 'demo';
  email_from: string;
  message: string;
}

export interface TripSummary {
  id: number;
  name: string;
  destination: string;
  start_date: string;
  end_date: string;
  currency: string;
  status: TripStatus;
  created_at: string | null;
  completed_at: string | null;
  member_count: number;
  expense_count: number;
  total_spend_paise: number;
  pending_settlement_paise: number;
  suggested_settlement_count: number;
  completed_settlement_count: number;
}

export interface Member {
  id: number;
  trip_id: number;
  name: string;
  email: string;
  created_at?: string | null;
}

export interface ExpenseShare {
  id: number;
  member_id: number;
  member_name: string;
  share_paise: number;
  percentage_bps: number | null;
}

export interface Expense {
  id: number;
  trip_id: number;
  title: string;
  amount_paise: number;
  category: string;
  expense_date: string;
  payer_id: number;
  payer_name: string;
  split_method: SplitMethod;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
  shares: ExpenseShare[];
}

export interface MemberBalance {
  member_id: number;
  member_name: string;
  member_email: string;
  total_paid_paise: number;
  total_share_paise: number;
  expense_net_paise: number;
  settlement_paid_paise: number;
  settlement_received_paise: number;
  remaining_net_paise: number;
  expenses_paid_count: number;
  expenses_participated_count: number;
}

export interface Settlement {
  id: number;
  trip_id: number;
  from_member_id: number;
  from_member_name: string;
  to_member_id: number;
  to_member_name: string;
  amount_paise: number;
  status: 'suggested' | 'completed';
  completed_at: string | null;
  created_at: string | null;
}

export interface CategoryStat {
  category: string;
  amount_paise: number;
  count: number;
  percentage: number;
}

export interface TripAnalytics {
  trip_id: number;
  total_spend_paise: number;
  expense_count: number;
  average_expense_paise: number;
  member_count: number;
  highest_category: CategoryStat | null;
  most_frequent_payer: {
    member_id: number;
    member_name: string;
    expenses_paid_count: number;
    total_paid_paise: number;
  } | null;
  largest_expense: {
    id: number;
    title: string;
    amount_paise: number;
    category: string;
    expense_date: string;
    payer_name: string;
  } | null;
  personal_expense_count: number;
  payer_excluded_count: number;
  category_breakdown: CategoryStat[];
  member_contributions: MemberBalance[];
  daily_spending: { date: string; amount_paise: number }[];
  split_breakdown: { method: string; count: number; amount_paise: number }[];
  insights: string[];
  all_categories: string[];
}

export interface EmailDelivery {
  id: number;
  trip_id: number;
  member_id: number;
  recipient_name: string;
  recipient_email: string;
  subject: string;
  html_body: string;
  status: 'sent' | 'demo' | 'failed';
  provider: 'resend' | 'smtp' | 'demo';
  error_message: string | null;
  sent_at: string | null;
  created_at: string | null;
}

export interface TripDetail extends TripSummary {
  members: Member[];
  expenses: Expense[];
  balances: MemberBalance[];
  settlements: {
    suggested: Settlement[];
    completed: Settlement[];
  };
  analytics: TripAnalytics;
  email_deliveries: EmailDelivery[];
  email_provider: EmailProviderStatus;
}

export interface RecentExpenseItem {
  id: number;
  trip_id: number;
  trip_name: string;
  trip_destination: string;
  title: string;
  amount_paise: number;
  category: string;
  expense_date: string;
  payer_name: string;
  split_method: SplitMethod;
  participant_count: number;
}

export interface DashboardData {
  total_trips: number;
  active_trips: number;
  completed_trips: number;
  total_expenditure_paise: number;
  total_owed_paise: number;
  total_receivable_paise: number;
  pending_settlement_count: number;
  completed_settlement_count: number;
  unread_notifications_count: number;
  email_provider: EmailProviderStatus;
  trips: TripSummary[];
  recent_expenses: RecentExpenseItem[];
  category_totals: { category: string; amount_paise: number }[];
}

export interface NotificationItem {
  id: number;
  trip_id: number | null;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string | null;
}
