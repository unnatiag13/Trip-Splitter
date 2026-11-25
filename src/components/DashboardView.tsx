import { useMemo, useState } from 'react';
import {
  ArrowDown,
  ArrowUpRight,
  Bell,
  CheckCircle2,
  Clock,
  Plus,
  Search,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { DashboardData, TripStatus } from '../types';
import {
  ANALYTICS_PALETTE,
  CATEGORY_COLOR_MAP,
  formatDateShort,
  formatINR,
} from '../utils/format';

interface DashboardViewProps {
  data: DashboardData;
  unreadCount: number;
  onSelectTrip: (tripId: number) => void;
  onNewTrip: () => void;
  onOpenNotifications: () => void;
}

export function DashboardView({
  data,
  unreadCount,
  onSelectTrip,
  onNewTrip,
  onOpenNotifications,
}: DashboardViewProps) {
  const [statusFilter, setStatusFilter] = useState<'all' | TripStatus>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const filteredTrips = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return data.trips.filter((t) => {
      if (statusFilter !== 'all' && t.status !== statusFilter) return false;
      if (!q) return true;
      return (
        t.name.toLowerCase().includes(q) ||
        t.destination.toLowerCase().includes(q)
      );
    });
  }, [data.trips, searchQuery, statusFilter]);

  const chartData = useMemo(
    () =>
      data.category_totals.map((c, idx) => ({
        category: c.category,
        amountRupees: Number((c.amount_paise / 100).toFixed(2)),
        amountPaise: c.amount_paise,
        color:
          CATEGORY_COLOR_MAP[c.category] ||
          ANALYTICS_PALETTE[idx % ANALYTICS_PALETTE.length],
      })),
    [data.category_totals]
  );

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <div className="min-h-screen bg-[#FAF9F7] text-[#29252A]">
      {/* Crisp 3-Zone Top Bar */}
      <header className="bg-white border-b border-[#EFE9EB] sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-10 h-16 flex items-center justify-between gap-8">
          <button
            type="button"
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
            className="inline-flex items-center gap-2.5 whitespace-nowrap shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#641C32] rounded"
          >
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
              className="shrink-0"
            >
              <path
                d="M3 3H13C17.9706 3 22 7.02944 22 12C22 16.9706 17.9706 21 13 21H3V3Z"
                fill="#641C32"
              />
              <path d="M3 3L11 12L3 21V3Z" fill="#873B52" />
            </svg>
            <span className="font-display text-lg font-bold tracking-tight">
              <span className="text-[#29252A]">Trip</span>
              <span className="text-[#641C32]">Ledger</span>
            </span>
          </button>

          <nav className="hidden md:flex items-center gap-7 text-sm font-medium text-[#524A4E]">
            <button
              type="button"
              onClick={() => scrollToSection('trips-directory')}
              className="hover:text-[#641C32] transition-colors whitespace-nowrap shrink-0"
            >
              Trips
            </button>
            <button
              type="button"
              onClick={() => scrollToSection('ledger-metrics')}
              className="hover:text-[#641C32] transition-colors whitespace-nowrap shrink-0"
            >
              Balances
            </button>
            <button
              type="button"
              onClick={() => scrollToSection('recent-activity')}
              className="hover:text-[#641C32] transition-colors whitespace-nowrap shrink-0"
            >
              Analytics
            </button>
            <button
              type="button"
              onClick={onOpenNotifications}
              className="inline-flex items-center gap-1.5 hover:text-[#641C32] transition-colors whitespace-nowrap shrink-0"
            >
              <Bell className="h-3.5 w-3.5" />
              <span>Notifications</span>
              {unreadCount > 0 && (
                <span className="font-mono text-xs font-semibold text-[#641C32] tabular-nums">
                  ({unreadCount})
                </span>
              )}
            </button>
          </nav>

          <div className="flex items-center gap-3 shrink-0">
            <button
              type="button"
              onClick={onOpenNotifications}
              aria-label="Notifications"
              className="md:hidden relative p-2 text-[#524A4E] hover:text-[#641C32] rounded-lg"
            >
              <Bell className="h-4 w-4" />
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 font-mono text-[10px] font-bold text-[#641C32]">
                  {unreadCount}
                </span>
              )}
            </button>
            <button
              type="button"
              onClick={onNewTrip}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#641C32] px-4 py-2 text-xs sm:text-sm font-medium text-white hover:bg-[#873B52] transition-colors whitespace-nowrap shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#641C32] focus-visible:ring-offset-2"
            >
              <Plus className="h-4 w-4" />
              <span>Add New Trip</span>
            </button>
          </div>
        </div>
      </header>

      {/* Gallery Hero Section */}
      <section className="bg-white border-b border-[#EFE9EB]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-10 py-12 lg:py-20 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-6 space-y-6">
            <h1
              className="font-display font-bold tracking-tight text-[#29252A] leading-[1.06]"
              style={{
                fontSize: 'clamp(2.35rem, 4.4vw, 3.75rem)',
                textWrap: 'balance',
              }}
            >
              Split Group
              <br />
              Expenses with{' '}
              <span className="text-[#B9788B]">Shared Clarity</span>
            </h1>

            <p className="text-base text-[#524A4E] leading-relaxed max-w-md">
              Plan trips, track shared payments in exact paise, and settle group balances in the fewest possible transfers.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-1">
              <button
                type="button"
                onClick={onNewTrip}
                className="inline-flex items-center gap-2 rounded-lg bg-[#641C32] px-6 py-3 text-sm font-medium text-white hover:bg-[#873B52] transition-colors whitespace-nowrap"
              >
                <Plus className="h-4 w-4" />
                <span>Add New Trip</span>
              </button>
              <button
                type="button"
                onClick={() => scrollToSection('trips-directory')}
                className="inline-flex items-center gap-2 rounded-lg border border-[#B9788B] bg-white px-5 py-3 text-sm font-medium text-[#641C32] hover:bg-[#F3E7EB]/50 transition-colors whitespace-nowrap"
              >
                <span>Explore Trips</span>
                <ArrowDown className="h-4 w-4" />
              </button>
            </div>

            <div className="pt-6 grid grid-cols-3 gap-6 max-w-lg">
              <div>
                <div className="font-display text-2xl sm:text-3xl font-bold font-mono tabular-nums text-[#3D9A9B]">
                  {data.total_trips}
                </div>
                <div className="mt-1 text-xs font-medium text-[#29252A]">
                  Trips Tracked
                </div>
              </div>
              <div>
                <div className="font-display text-2xl sm:text-3xl font-bold font-mono tabular-nums text-[#5B88B8]">
                  {formatINR(data.total_expenditure_paise).replace('.00', '')}
                </div>
                <div className="mt-1 text-xs font-medium text-[#29252A]">
                  Total Expenditure
                </div>
              </div>
              <div>
                <div className="font-display text-2xl sm:text-3xl font-bold font-mono tabular-nums text-[#B9788B]">
                  {data.pending_settlement_count}
                </div>
                <div className="mt-1 text-xs font-medium text-[#29252A]">
                  Pending Transfers
                </div>
              </div>
            </div>
          </div>

          <div className="lg:col-span-6 flex justify-center lg:justify-end">
            <div className="w-full max-w-[430px] aspect-square">
              <svg
                viewBox="0 0 420 420"
                className="w-full h-full"
                role="img"
                aria-label="Geometric modular composition in maroon, burgundy, dusty rose, blush, and soft teal"
              >
                <path
                  d="M 65 0 H 140 V 140 H 0 V 65 A 65 65 0 0 1 65 0 Z"
                  fill="#641C32"
                />
                <polygon points="210,0 280,70 210,140 140,70" fill="#873B52" />
                <path
                  d="M 280 0 H 310 A 110 110 0 0 1 420 110 V 170 A 110 110 0 0 1 310 280 H 280 V 0 Z"
                  fill="#B9788B"
                />
                <rect
                  x="11"
                  y="151"
                  width="118"
                  height="118"
                  fill="#FFFFFF"
                  stroke="#D5A6B4"
                  strokeWidth="22"
                />
                <circle cx="210" cy="210" r="70" fill="#D2ECEC" />
                <path
                  d="M 0 335 A 55 55 0 0 1 55 280 H 140 V 420 H 65 A 65 65 0 0 1 0 355 V 335 Z"
                  fill="#C88D9E"
                />
                <polygon points="210,280 280,420 140,420" fill="#D2ECEC" />
                <polygon points="210,336 242,398 178,398" fill="#FFFFFF" />
                <path
                  d="M 280 280 A 140 140 0 0 1 420 420 H 280 V 280 Z"
                  fill="#F3E7EB"
                />
                <path
                  d="M 280 340 A 80 80 0 0 1 360 420 H 280 V 340 Z"
                  fill="#B9788B"
                  opacity="0.45"
                />
              </svg>
            </div>
          </div>
        </div>
      </section>

      {/* Main Dashboard Workspace Below Hero */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-10 py-10 space-y-8">
        {/* Clean 4-Metric KPI Strip */}
        <section
          id="ledger-metrics"
          className="rounded-xl bg-white border border-[#E9E2E4] grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-[#EFE9EB]"
        >
          <div className="p-5">
            <div className="text-xs font-medium text-[#524A4E]">Total Trips</div>
            <div className="mt-2 font-mono text-2xl font-bold tabular-nums text-[#29252A]">
              {data.total_trips}
            </div>
          </div>

          <div className="p-5">
            <div className="text-xs font-medium text-[#524A4E]">Total Expenditure</div>
            <div className="mt-2 font-mono text-2xl font-bold tabular-nums text-[#29252A]">
              {formatINR(data.total_expenditure_paise)}
            </div>
          </div>

          <div className="p-5">
            <div className="text-xs font-medium text-[#524A4E]">Pending Settlement</div>
            <div className="mt-2 font-mono text-2xl font-bold tabular-nums text-[#641C32]">
              {formatINR(data.total_owed_paise)}
            </div>
          </div>

          <div className="p-5">
            <div className="text-xs font-medium text-[#524A4E]">Completed Payments</div>
            <div className="mt-2 font-mono text-2xl font-bold tabular-nums text-[#2F6F4E]">
              {data.completed_settlement_count}
            </div>
          </div>
        </section>

        {/* Trips Directory */}
        <section
          id="trips-directory"
          className="rounded-xl bg-white border border-[#E9E2E4] overflow-hidden"
        >
          <div className="flex flex-wrap items-center justify-between gap-4 px-5 py-4 border-b border-[#EFE9EB]">
            <h2 className="font-display text-base font-semibold text-[#29252A]">
              Trips Directory
            </h2>

            <div className="flex flex-wrap items-center gap-3">
              <div className="relative">
                <Search className="h-4 w-4 text-[#8E8489] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type="search"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search trips"
                  className="w-52 rounded-lg border border-[#DDD4D7] bg-[#FAF9F7] pl-9 pr-3 py-1.5 text-xs text-[#29252A] focus:bg-white focus:border-[#641C32] focus:outline-none"
                />
              </div>

              <div className="flex items-center gap-1 p-1 rounded-lg bg-[#F3E7EB]/60 border border-[#E9E2E4]">
                {(['all', 'active', 'completed'] as const).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setStatusFilter(tab)}
                    className={`px-3 py-1 rounded-md text-xs font-medium transition-colors whitespace-nowrap ${
                      statusFilter === tab
                        ? 'bg-white text-[#641C32] shadow-sm'
                        : 'text-[#524A4E] hover:text-[#29252A]'
                    }`}
                  >
                    {tab === 'all' ? 'All' : tab === 'active' ? 'Active' : 'Completed'}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {filteredTrips.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <p className="text-sm text-[#524A4E]">
                {data.trips.length === 0
                  ? 'No trips created yet. Start by creating your first group trip.'
                  : 'No trips match your current filter.'}
              </p>
              {data.trips.length === 0 && (
                <button
                  type="button"
                  onClick={onNewTrip}
                  className="mt-4 inline-flex items-center gap-2 rounded-lg bg-[#641C32] px-4 py-2 text-sm font-medium text-white hover:bg-[#873B52]"
                >
                  <Plus className="h-4 w-4" />
                  <span>Create First Trip</span>
                </button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-[#FAF9F7] border-b border-[#EFE9EB] text-xs font-medium text-[#524A4E]">
                    <th className="py-3 px-5">Trip</th>
                    <th className="py-3 px-4">Date</th>
                    <th className="py-3 px-4 text-right">Total Spend</th>
                    <th className="py-3 px-4 text-right">Pending</th>
                    <th className="py-3 px-5 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#EFE9EB] text-sm">
                  {filteredTrips.map((trip) => (
                    <tr
                      key={trip.id}
                      onClick={() => onSelectTrip(trip.id)}
                      className="hover:bg-[#FAF9F7] cursor-pointer transition-colors"
                    >
                      <td className="py-3.5 px-5 font-semibold text-[#29252A]">
                        <div className="flex items-center gap-1.5">
                          <span>{trip.name}</span>
                          <ArrowUpRight className="h-3.5 w-3.5 text-[#873B52]" />
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-xs text-[#524A4E] whitespace-nowrap font-mono tabular-nums">
                        {formatDateShort(trip.start_date)}
                      </td>
                      <td className="py-3.5 px-4 text-right font-mono font-semibold tabular-nums text-[#29252A]">
                        {formatINR(trip.total_spend_paise)}
                      </td>
                      <td className="py-3.5 px-4 text-right font-mono tabular-nums text-[#641C32]">
                        {trip.pending_settlement_paise > 0
                          ? formatINR(trip.pending_settlement_paise)
                          : '₹0.00'}
                      </td>
                      <td className="py-3.5 px-5 text-right whitespace-nowrap">
                        {trip.status === 'active' ? (
                          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-[#2F6F4E]">
                            <Clock className="h-3.5 w-3.5" />
                            <span>Active</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-[#641C32]">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            <span>Completed</span>
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Bottom 2-column grid: Recent Expenses + Category Analytics */}
        <div
          id="recent-activity"
          className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch"
        >
          <section className="lg:col-span-7 rounded-xl bg-white border border-[#E9E2E4] flex flex-col overflow-hidden">
            <div className="px-5 py-4 border-b border-[#EFE9EB]">
              <h2 className="font-display text-base font-semibold text-[#29252A]">
                Recent Expenses
              </h2>
            </div>
            {data.recent_expenses.length === 0 ? (
              <div className="p-8 text-center text-sm text-[#524A4E]">
                No expenses recorded yet.
              </div>
            ) : (
              <div className="divide-y divide-[#EFE9EB] flex-1">
                {data.recent_expenses.slice(0, 8).map((exp) => (
                  <button
                    key={exp.id}
                    type="button"
                    onClick={() => onSelectTrip(exp.trip_id)}
                    className="w-full text-left px-5 py-3.5 flex items-center justify-between gap-4 hover:bg-[#FAF9F7] transition-colors"
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-[#29252A] truncate">
                        {exp.title}
                      </div>
                      <div className="mt-0.5 text-xs text-[#6E656B] truncate">
                        {exp.trip_name}
                      </div>
                    </div>
                    <div className="font-mono text-sm font-semibold tabular-nums text-[#29252A] shrink-0">
                      {formatINR(exp.amount_paise)}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </section>

          <section className="lg:col-span-5 rounded-xl bg-white border border-[#E9E2E4] flex flex-col overflow-hidden">
            <div className="px-5 py-4 border-b border-[#EFE9EB]">
              <h2 className="font-display text-base font-semibold text-[#29252A]">
                Spending by Category
              </h2>
            </div>
            <div className="p-5 flex-1 flex flex-col justify-between">
              {chartData.length === 0 ? (
                <div className="py-12 text-center text-sm text-[#524A4E]">
                  Add expenses to view category distribution.
                </div>
              ) : (
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={chartData}
                      layout="vertical"
                      margin={{ top: 4, right: 16, left: 10, bottom: 4 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#EFE9EB" horizontal={false} />
                      <XAxis
                        type="number"
                        tick={{ fontSize: 11, fill: '#6E656B' }}
                        tickFormatter={(val) => `₹${Math.round(Number(val) / 1000)}k`}
                        axisLine={{ stroke: '#E9E2E4' }}
                        tickLine={false}
                      />
                      <YAxis
                        dataKey="category"
                        type="category"
                        width={98}
                        tick={{ fontSize: 12, fill: '#29252A' }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        formatter={(value: unknown) => [
                          formatINR(Math.round(Number(value || 0) * 100)),
                          'Spend',
                        ]}
                        contentStyle={{
                          borderRadius: '8px',
                          border: '1px solid #E9E2E4',
                          fontSize: '12px',
                        }}
                      />
                      <Bar dataKey="amountRupees" radius={[0, 6, 6, 0]} barSize={20}>
                        {chartData.map((entry) => (
                          <Cell key={entry.category} fill={entry.color} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
