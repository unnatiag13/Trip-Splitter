import { useMemo, useState } from 'react';
import { ArrowUpRight, Bell, Check, CheckCheck } from 'lucide-react';
import type { NotificationItem } from '../types';
import { formatTimestamp } from '../utils/format';

interface NotificationsViewProps {
  items: NotificationItem[];
  unreadCount: number;
  onMarkRead: (id: number) => Promise<void>;
  onMarkAllRead: () => Promise<void>;
  onOpenTrip: (tripId: number) => void;
}

export function NotificationsView({
  items,
  unreadCount,
  onMarkRead,
  onMarkAllRead,
  onOpenTrip,
}: NotificationsViewProps) {
  const [filter, setFilter] = useState<'all' | 'unread'>('all');

  const visibleItems = useMemo(
    () => (filter === 'unread' ? items.filter((i) => !i.is_read) : items),
    [filter, items]
  );

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-7 space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-[#29252A]">
            Notifications
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 p-1 rounded-lg bg-[#F3E7EB]/60 border border-[#E9E2E4]">
            <button
              type="button"
              onClick={() => setFilter('all')}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors whitespace-nowrap ${
                filter === 'all'
                  ? 'bg-white text-[#641C32] shadow-sm'
                  : 'text-[#524A4E] hover:text-[#29252A]'
              }`}
            >
              All ({items.length})
            </button>
            <button
              type="button"
              onClick={() => setFilter('unread')}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors whitespace-nowrap ${
                filter === 'unread'
                  ? 'bg-white text-[#641C32] shadow-sm'
                  : 'text-[#524A4E] hover:text-[#29252A]'
              }`}
            >
              Unread ({unreadCount})
            </button>
          </div>

          {unreadCount > 0 && (
            <button
              type="button"
              onClick={onMarkAllRead}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[#DDD4D7] bg-white px-3.5 py-2 text-xs font-medium text-[#641C32] hover:bg-[#F3E7EB] whitespace-nowrap"
            >
              <CheckCheck className="h-3.5 w-3.5" />
              <span>Mark All Read</span>
            </button>
          )}
        </div>
      </div>

      <div className="rounded-xl bg-white border border-[#E9E2E4] overflow-hidden divide-y divide-[#EFE9EB]">
        {visibleItems.length === 0 ? (
          <div className="py-12 px-6 text-center">
            <Bell className="h-8 w-8 mx-auto text-[#B9788B] mb-2" />
            <p className="text-sm text-[#524A4E]">
              {filter === 'unread'
                ? 'You have no unread notifications.'
                : 'No activity notifications yet.'}
            </p>
          </div>
        ) : (
          visibleItems.map((n) => (
            <div
              key={n.id}
              className={`px-5 py-4 flex items-start justify-between gap-4 ${
                n.is_read ? 'bg-white' : 'bg-[#F3E7EB]/30'
              }`}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-[#29252A]">
                    {n.title}
                  </span>
                  {!n.is_read && (
                    <span className="text-[11px] font-medium text-[#641C32]">
                      · Unread
                    </span>
                  )}
                </div>
                <p className="mt-1 text-sm text-[#524A4E] leading-relaxed">
                  {n.message}
                </p>
                <div className="mt-1.5 flex items-center gap-3 text-xs text-[#6E656B]">
                  <span className="font-mono tabular-nums">
                    {formatTimestamp(n.created_at)}
                  </span>
                  {n.trip_id && (
                    <button
                      type="button"
                      onClick={() => onOpenTrip(n.trip_id!)}
                      className="inline-flex items-center gap-1 font-medium text-[#641C32] hover:underline"
                    >
                      <span>View Trip</span>
                      <ArrowUpRight className="h-3 w-3" />
                    </button>
                  )}
                </div>
              </div>

              {!n.is_read && (
                <button
                  type="button"
                  onClick={() => onMarkRead(n.id)}
                  className="shrink-0 inline-flex items-center gap-1 rounded-lg border border-[#DDD4D7] bg-white px-2.5 py-1.5 text-xs font-medium text-[#524A4E] hover:text-[#641C32] hover:border-[#B9788B] whitespace-nowrap"
                >
                  <Check className="h-3.5 w-3.5" />
                  <span>Mark Read</span>
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
