import type {
  DashboardData,
  EmailDelivery,
  Expense,
  Member,
  NotificationItem,
  SplitMethod,
  TripDetail,
  TripSummary,
} from '../types';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers || {}),
    },
    ...options,
  });

  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data?.detail === 'string') {
        message = data.detail;
      } else if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
        const first = data.detail[0];
        const loc = Array.isArray(first.loc)
          ? first.loc.filter((p: unknown) => p !== 'body').join('.')
          : '';
        message = loc ? `${loc}: ${first.msg}` : first.msg;
      }
    } catch {
      // ignore non-json error bodies
    }
    throw new Error(message);
  }

  return res.json() as Promise<T>;
}

export const api = {
  getDashboard: () => request<DashboardData>('/api/dashboard'),

  listTrips: () => request<TripSummary[]>('/api/trips'),

  getTrip: (tripId: number) => request<TripDetail>(`/api/trips/${tripId}`),

  createTrip: (payload: {
    name: string;
    destination?: string;
    start_date: string;
    end_date?: string;
    currency?: string;
    members: { name: string; email: string }[];
  }) =>
    request<TripDetail>('/api/trips', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateTrip: (
    tripId: number,
    payload: {
      name?: string;
      destination?: string;
      start_date?: string;
      end_date?: string;
    }
  ) =>
    request<TripDetail>(`/api/trips/${tripId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deleteTrip: (tripId: number) =>
    request<{ deleted: boolean; trip_id: number }>(`/api/trips/${tripId}`, {
      method: 'DELETE',
    }),

  addMember: (tripId: number, payload: { name: string; email: string }) =>
    request<Member>(`/api/trips/${tripId}/members`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  removeMember: (tripId: number, memberId: number) =>
    request<{ deleted: boolean; member_id: number }>(
      `/api/trips/${tripId}/members/${memberId}`,
      { method: 'DELETE' }
    ),

  createExpense: (
    tripId: number,
    payload: {
      title: string;
      amount_paise: number;
      category: string;
      expense_date: string;
      payer_id: number;
      split_method: SplitMethod;
      participants: {
        member_id: number;
        share_paise?: number;
        percentage?: number;
        percentage_bps?: number;
      }[];
      notes?: string | null;
    }
  ) =>
    request<Expense>(`/api/trips/${tripId}/expenses`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateExpense: (
    tripId: number,
    expenseId: number,
    payload: {
      title: string;
      amount_paise: number;
      category: string;
      expense_date: string;
      payer_id: number;
      split_method: SplitMethod;
      participants: {
        member_id: number;
        share_paise?: number;
        percentage?: number;
        percentage_bps?: number;
      }[];
      notes?: string | null;
    }
  ) =>
    request<Expense>(`/api/trips/${tripId}/expenses/${expenseId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  deleteExpense: (tripId: number, expenseId: number) =>
    request<{ deleted: boolean; expense_id: number }>(
      `/api/trips/${tripId}/expenses/${expenseId}`,
      { method: 'DELETE' }
    ),

  completeSettlement: (tripId: number, settlementId: number) =>
    request(`/api/trips/${tripId}/settlements/${settlementId}/complete`, {
      method: 'POST',
    }),

  revertSettlement: (tripId: number, settlementId: number) =>
    request(`/api/trips/${tripId}/settlements/${settlementId}/complete`, {
      method: 'DELETE',
    }),

  sendReminders: (tripId: number) =>
    request<{ created_count: number }>(`/api/trips/${tripId}/settlements/remind`, {
      method: 'POST',
    }),

  endTrip: (tripId: number) =>
    request<TripDetail>(`/api/trips/${tripId}/end`, {
      method: 'POST',
    }),

  reopenTrip: (tripId: number) =>
    request<TripDetail>(`/api/trips/${tripId}/reopen`, {
      method: 'POST',
    }),

  resendEmail: (tripId: number, deliveryId: number) =>
    request<EmailDelivery>(`/api/trips/${tripId}/emails/${deliveryId}/resend`, {
      method: 'POST',
    }),

  getViewEmailUrl: (tripId: number, deliveryId: number) =>
    `/api/trips/${tripId}/emails/${deliveryId}/view`,

  getDownloadEmailUrl: (tripId: number, deliveryId: number) =>
    `/api/trips/${tripId}/emails/${deliveryId}/download`,

  listNotifications: () =>
    request<{ unread_count: number; items: NotificationItem[] }>('/api/notifications'),

  markNotificationRead: (id: number) =>
    request<{ id: number; is_read: boolean }>(`/api/notifications/${id}/read`, {
      method: 'POST',
    }),

  markAllNotificationsRead: () =>
    request<{ updated: boolean }>('/api/notifications/read-all', {
      method: 'POST',
    }),
};
