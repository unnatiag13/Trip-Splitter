import { useMemo, useState, type FormEvent } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  BellRing,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Edit3,
  Lock,
  Mail,
  Plus,
  RotateCcw,
  Search,
  Trash2,
  UserPlus,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { Expense, TripDetail } from '../types';
import {
  ANALYTICS_PALETTE,
  CATEGORY_COLOR_MAP,
  EXPENSE_CATEGORIES,
  formatDateShort,
  formatINR,
  splitMethodLabel,
} from '../utils/format';

export type TripTab = 'expenses' | 'settle' | 'analytics' | 'members';

interface TripDetailViewProps {
  trip: TripDetail;
  onBack: () => void;
  onEditTrip: () => void;
  onDeleteTrip: () => Promise<void>;
  onAddExpense: () => void;
  onEditExpense: (expense: Expense) => void;
  onDeleteExpense: (expenseId: number) => Promise<void>;
  onAddMember: (name: string, email: string) => Promise<void>;
  onRemoveMember: (memberId: number) => Promise<void>;
  onCompleteSettlement: (settlementId: number) => Promise<void>;
  onRevertSettlement: (settlementId: number) => Promise<void>;
  onSendReminders: () => Promise<void>;
  onOpenEndTrip: () => void;
  onOpenReopenTrip: () => void;
  onOpenEmails: () => void;
}

export function TripDetailView({
  trip,
  onBack,
  onEditTrip,
  onDeleteTrip,
  onAddExpense,
  onEditExpense,
  onDeleteExpense,
  onAddMember,
  onRemoveMember,
  onCompleteSettlement,
  onRevertSettlement,
  onSendReminders,
  onOpenEndTrip,
  onOpenReopenTrip,
  onOpenEmails,
}: TripDetailViewProps) {
  const [activeTab, setActiveTab] = useState<TripTab>('expenses');
  const [expenseSearch, setExpenseSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [expandedExpenseId, setExpandedExpenseId] = useState<number | null>(null);
  const [confirmDeleteExpenseId, setConfirmDeleteExpenseId] = useState<number | null>(null);
  const [confirmDeleteTrip, setConfirmDeleteTrip] = useState(false);

  const [newMemberName, setNewMemberName] = useState('');
  const [newMemberEmail, setNewMemberEmail] = useState('');
  const [memberError, setMemberError] = useState<string | null>(null);
  const [addingMember, setAddingMember] = useState(false);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const isCompleted = trip.status === 'completed';

  const filteredExpenses = useMemo(() => {
    const q = expenseSearch.trim().toLowerCase();
    return trip.expenses.filter((exp) => {
      if (categoryFilter !== 'all' && exp.category !== categoryFilter) return false;
      if (!q) return true;
      return (
        exp.title.toLowerCase().includes(q) ||
        exp.payer_name.toLowerCase().includes(q)
      );
    });
  }, [categoryFilter, expenseSearch, trip.expenses]);

  const handleAddMemberSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setMemberError(null);
    if (!newMemberName.trim() || !newMemberEmail.trim()) {
      setMemberError('Enter both name and email address.');
      return;
    }
    setAddingMember(true);
    try {
      await onAddMember(newMemberName.trim(), newMemberEmail.trim());
      setNewMemberName('');
      setNewMemberEmail('');
    } catch (err) {
      setMemberError(err instanceof Error ? err.message : 'Failed to add member.');
    } finally {
      setAddingMember(false);
    }
  };

  const handleRemoveMemberClick = async (memberId: number) => {
    setMemberError(null);
    setBusyId(memberId);
    try {
      await onRemoveMember(memberId);
    } catch (err) {
      setMemberError(err instanceof Error ? err.message : 'Failed to remove member.');
    } finally {
      setBusyId(null);
    }
  };

  const handleSendRemindersClick = async () => {
    await onSendReminders();
    setActionFeedback('Settlement reminders sent.');
    setTimeout(() => setActionFeedback(null), 3500);
  };

  const balanceChartData = useMemo(
    () =>
      trip.balances.map((b) => ({
        name: b.member_name.split(' ')[0],
        paidRupees: Number((b.total_paid_paise / 100).toFixed(2)),
        shareRupees: Number((b.total_share_paise / 100).toFixed(2)),
      })),
    [trip.balances]
  );

  const categoryChartData = useMemo(
    () =>
      trip.analytics.category_breakdown.map((c, idx) => ({
        ...c,
        amountRupees: Number((c.amount_paise / 100).toFixed(2)),
        color:
          CATEGORY_COLOR_MAP[c.category] ||
          ANALYTICS_PALETTE[idx % ANALYTICS_PALETTE.length],
      })),
    [trip.analytics.category_breakdown]
  );

  const dailyChartData = useMemo(
    () =>
      trip.analytics.daily_spending.map((d) => ({
        date: d.date.slice(5),
        amountRupees: Number((d.amount_paise / 100).toFixed(2)),
      })),
    [trip.analytics.daily_spending]
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-7 space-y-6">
      {/* Header */}
      <div className="space-y-3">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-[#524A4E] hover:text-[#641C32] transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Dashboard</span>
        </button>

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-baseline gap-3">
            <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-[#29252A]">
              {trip.name}
            </h1>
            <span className="font-mono text-xs text-[#6E656B] tabular-nums">
              {formatDateShort(trip.start_date)}
            </span>
            {isCompleted ? (
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#641C32]">
                <Lock className="h-3.5 w-3.5" />
                <span>Completed</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#2F6F4E]">
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span>Active</span>
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            {!isCompleted ? (
              <>
                <button
                  type="button"
                  onClick={onOpenEndTrip}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-[#B9788B] bg-[#F3E7EB] px-3.5 py-2 text-xs font-medium text-[#641C32] hover:bg-[#ead8de] whitespace-nowrap"
                >
                  <Lock className="h-3.5 w-3.5" />
                  <span>End Trip</span>
                </button>
                <button
                  type="button"
                  onClick={onAddExpense}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[#641C32] px-4 py-2 text-xs font-medium text-white hover:bg-[#873B52] whitespace-nowrap"
                >
                  <Plus className="h-4 w-4" />
                  <span>Add Expense</span>
                </button>
              </>
            ) : (
              <>
                {trip.email_deliveries.length > 0 && (
                  <button
                    type="button"
                    onClick={onOpenEmails}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-[#DDD4D7] bg-white px-3.5 py-2 text-xs font-medium text-[#29252A] hover:bg-[#FAF9F7] whitespace-nowrap"
                  >
                    <Mail className="h-3.5 w-3.5 text-[#641C32]" />
                    <span>Open Summaries ({trip.email_deliveries.length})</span>
                  </button>
                )}
                <button
                  type="button"
                  onClick={onOpenReopenTrip}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[#641C32] px-4 py-2 text-xs font-medium text-white hover:bg-[#873B52] whitespace-nowrap"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  <span>Reopen Trip</span>
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {isCompleted && (
        <div className="rounded-xl bg-[#F3E7EB]/70 border border-[#DFC8D0] px-5 py-3 flex flex-wrap items-center justify-between gap-3 text-sm text-[#641C32]">
          <div className="flex items-center gap-2">
            <Lock className="h-4 w-4 shrink-0" />
            <span>Trip is completed and read-only.</span>
          </div>
          {trip.email_deliveries.length > 0 && (
            <button
              type="button"
              onClick={onOpenEmails}
              className="text-xs font-semibold hover:underline whitespace-nowrap"
            >
              View &amp; Download HTML Statements
            </button>
          )}
        </div>
      )}

      {actionFeedback && (
        <div className="rounded-xl bg-white border border-[#B9788B] px-4 py-3 text-sm text-[#641C32]">
          {actionFeedback}
        </div>
      )}

      {/* 4 Focused Non-Redundant Tabs */}
      <div className="flex items-center gap-1 p-1 rounded-xl bg-[#F3E7EB]/60 border border-[#E9E2E4] overflow-x-auto">
        {(
          [
            { id: 'expenses', label: `Expenses (${trip.expenses.length})` },
            { id: 'settle', label: 'Balances & Settlements' },
            { id: 'analytics', label: 'Analytics' },
            { id: 'members', label: `Members (${trip.members.length})` },
          ] as { id: TripTab; label: string }[]
        ).map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2 rounded-lg text-xs sm:text-sm font-medium transition-colors whitespace-nowrap shrink-0 ${
              activeTab === t.id
                ? 'bg-white text-[#641C32] shadow-sm'
                : 'text-[#524A4E] hover:text-[#29252A]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* TAB 1: EXPENSES ONLY */}
      {activeTab === 'expenses' && (
        <section className="rounded-xl bg-white border border-[#E9E2E4] overflow-hidden">
          <div className="p-4 sm:px-5 border-b border-[#EFE9EB] flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2.5">
              <div className="relative">
                <Search className="h-4 w-4 text-[#8E8489] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type="search"
                  value={expenseSearch}
                  onChange={(e) => setExpenseSearch(e.target.value)}
                  placeholder="Search expenses"
                  className="w-52 rounded-lg border border-[#DDD4D7] bg-[#FAF9F7] pl-9 pr-3 py-1.5 text-xs text-[#29252A] focus:bg-white focus:border-[#641C32] focus:outline-none"
                />
              </div>

              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                aria-label="Filter by category"
                className="rounded-lg border border-[#DDD4D7] bg-white px-3 py-1.5 text-xs text-[#29252A] focus:border-[#641C32] focus:outline-none"
              >
                <option value="all">All Categories</option>
                {EXPENSE_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            <div className="font-mono text-sm font-semibold tabular-nums text-[#29252A]">
              Total: {formatINR(trip.total_spend_paise)}
            </div>
          </div>

          {filteredExpenses.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <p className="text-sm text-[#524A4E]">
                {trip.expenses.length === 0
                  ? 'No expenses logged yet.'
                  : 'No matching expenses found.'}
              </p>
              {!isCompleted && trip.expenses.length === 0 && (
                <button
                  type="button"
                  onClick={onAddExpense}
                  className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-[#641C32] px-4 py-2 text-sm font-medium text-white hover:bg-[#873B52]"
                >
                  <Plus className="h-4 w-4" />
                  <span>Add First Expense</span>
                </button>
              )}
            </div>
          ) : (
            <div className="divide-y divide-[#EFE9EB]">
              {filteredExpenses.map((exp) => {
                const isExpanded = expandedExpenseId === exp.id;
                return (
                  <div key={exp.id} className="bg-white">
                    <div className="px-5 py-3.5 flex flex-wrap sm:flex-nowrap items-center justify-between gap-4 hover:bg-[#FAF9F7] transition-colors">
                      <button
                        type="button"
                        onClick={() => setExpandedExpenseId(isExpanded ? null : exp.id)}
                        className="flex-1 min-w-0 text-left flex items-center gap-3"
                      >
                        <span className="text-[#8E8489] shrink-0">
                          {isExpanded ? (
                            <ChevronUp className="h-4 w-4" />
                          ) : (
                            <ChevronDown className="h-4 w-4" />
                          )}
                        </span>
                        <div className="min-w-0 flex-1 grid grid-cols-1 sm:grid-cols-12 gap-1 sm:gap-4 items-center">
                          <span className="sm:col-span-5 text-sm font-semibold text-[#29252A] truncate">
                            {exp.title}
                          </span>
                          <span className="sm:col-span-3 text-xs text-[#524A4E] truncate">
                            Paid by {exp.payer_name}
                          </span>
                          <span className="sm:col-span-2 text-xs text-[#524A4E]">
                            {exp.category}
                          </span>
                          <span className="sm:col-span-2 text-xs font-mono tabular-nums text-[#6E656B]">
                            {formatDateShort(exp.expense_date)}
                          </span>
                        </div>
                      </button>

                      <div className="flex items-center gap-3 shrink-0">
                        <div className="font-mono text-sm font-bold tabular-nums text-[#29252A]">
                          {formatINR(exp.amount_paise)}
                        </div>

                        {!isCompleted && (
                          <div className="flex items-center gap-1">
                            <button
                              type="button"
                              onClick={() => onEditExpense(exp)}
                              aria-label={`Edit ${exp.title}`}
                              className="p-1.5 rounded-lg text-[#6E656B] hover:text-[#641C32] hover:bg-[#F3E7EB]"
                            >
                              <Edit3 className="h-3.5 w-3.5" />
                            </button>
                            {confirmDeleteExpenseId === exp.id ? (
                              <div className="flex items-center gap-1">
                                <button
                                  type="button"
                                  onClick={async () => {
                                    await onDeleteExpense(exp.id);
                                    setConfirmDeleteExpenseId(null);
                                  }}
                                  className="px-2 py-1 rounded bg-[#641C32] text-white text-[11px] font-medium"
                                >
                                  Delete
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setConfirmDeleteExpenseId(null)}
                                  className="px-2 py-1 rounded border border-[#DDD4D7] text-[11px] text-[#524A4E]"
                                >
                                  Cancel
                                </button>
                              </div>
                            ) : (
                              <button
                                type="button"
                                onClick={() => setConfirmDeleteExpenseId(exp.id)}
                                aria-label={`Delete ${exp.title}`}
                                className="p-1.5 rounded-lg text-[#6E656B] hover:text-[#641C32] hover:bg-[#F3E7EB]"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="px-12 pb-4 pt-2 bg-[#FAF9F7] border-t border-[#EFE9EB] space-y-2">
                        <div className="text-xs font-medium text-[#524A4E]">
                          {splitMethodLabel(exp.split_method)} split across {exp.shares.length} participants
                          {exp.notes ? ` · ${exp.notes}` : ''}
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-1.5">
                          {exp.shares.map((sh) => (
                            <div
                              key={sh.id}
                              className="flex items-center justify-between text-xs py-1 border-b border-[#EFE9EB]"
                            >
                              <span className="text-[#29252A] truncate">
                                {sh.member_name}
                                {sh.percentage_bps !== null && (
                                  <span className="ml-1.5 font-mono text-[#6E656B]">
                                    ({(sh.percentage_bps / 100).toFixed(1)}%)
                                  </span>
                                )}
                              </span>
                              <span className="font-mono font-semibold tabular-nums text-[#29252A]">
                                {formatINR(sh.share_paise)}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      {/* TAB 2: BALANCES & SETTLEMENTS (CONSOLIDATED, ZERO DUPLICATION) */}
      {activeTab === 'settle' && (
        <div className="space-y-6">
          {/* Member Net Balances */}
          <section className="rounded-xl bg-white border border-[#E9E2E4] overflow-hidden">
            <div className="px-5 py-4 border-b border-[#EFE9EB]">
              <h2 className="font-display text-base font-semibold text-[#29252A]">
                Member Balances
              </h2>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-[#FAF9F7] border-b border-[#EFE9EB] text-xs font-medium text-[#524A4E]">
                    <th className="py-3 px-5">Member</th>
                    <th className="py-3 px-4 text-right">Paid</th>
                    <th className="py-3 px-4 text-right">Share</th>
                    <th className="py-3 px-4 text-right">Remaining Balance</th>
                    <th className="py-3 px-5 text-right">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#EFE9EB] text-sm">
                  {trip.balances.map((b) => (
                    <tr key={b.member_id} className="hover:bg-[#FAF9F7]">
                      <td className="py-3.5 px-5 font-semibold text-[#29252A]">
                        {b.member_name}
                      </td>
                      <td className="py-3.5 px-4 text-right font-mono tabular-nums text-[#29252A]">
                        {formatINR(b.total_paid_paise)}
                      </td>
                      <td className="py-3.5 px-4 text-right font-mono tabular-nums text-[#29252A]">
                        {formatINR(b.total_share_paise)}
                      </td>
                      <td
                        className={`py-3.5 px-4 text-right font-mono font-bold tabular-nums ${
                          b.remaining_net_paise > 0
                            ? 'text-[#2F6F4E]'
                            : b.remaining_net_paise < 0
                            ? 'text-[#641C32]'
                            : 'text-[#6E656B]'
                        }`}
                      >
                        {formatINR(b.remaining_net_paise, true)}
                      </td>
                      <td className="py-3.5 px-5 text-right text-xs font-medium whitespace-nowrap">
                        {b.remaining_net_paise > 0 ? (
                          <span className="text-[#2F6F4E]">Receives</span>
                        ) : b.remaining_net_paise < 0 ? (
                          <span className="text-[#641C32]">Owes</span>
                        ) : (
                          <span className="text-[#6E656B]">Settled</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Suggested Minimum-Transaction Settlements */}
          <section className="rounded-xl bg-white border border-[#E9E2E4] overflow-hidden">
            <div className="px-5 py-4 border-b border-[#EFE9EB] flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-display text-base font-semibold text-[#29252A]">
                Suggested Settlements ({trip.settlements.suggested.length})
              </h2>
              <button
                type="button"
                onClick={handleSendRemindersClick}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[#DDD4D7] bg-white px-3.5 py-1.5 text-xs font-medium text-[#641C32] hover:bg-[#F3E7EB] whitespace-nowrap"
              >
                <BellRing className="h-3.5 w-3.5" />
                <span>Send Reminders</span>
              </button>
            </div>

            {trip.settlements.suggested.length === 0 ? (
              <div className="px-6 py-10 text-center text-sm text-[#524A4E]">
                Everyone is settled up.
              </div>
            ) : (
              <div className="divide-y divide-[#EFE9EB]">
                {trip.settlements.suggested.map((st) => (
                  <div
                    key={st.id}
                    className="px-5 py-4 flex flex-wrap items-center justify-between gap-4"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="text-sm font-semibold text-[#29252A]">
                        {st.from_member_name}
                      </span>
                      <ArrowRight className="h-4 w-4 text-[#873B52] shrink-0" />
                      <span className="text-sm font-semibold text-[#29252A]">
                        {st.to_member_name}
                      </span>
                    </div>

                    <div className="flex items-center gap-4 shrink-0">
                      <span className="font-mono text-base font-bold tabular-nums text-[#641C32]">
                        {formatINR(st.amount_paise)}
                      </span>
                      {!isCompleted && (
                        <button
                          type="button"
                          disabled={busyId === st.id}
                          onClick={async () => {
                            setBusyId(st.id);
                            try {
                              await onCompleteSettlement(st.id);
                            } finally {
                              setBusyId(null);
                            }
                          }}
                          className="rounded-lg bg-[#641C32] px-3.5 py-1.5 text-xs font-medium text-white hover:bg-[#873B52] disabled:opacity-60 whitespace-nowrap"
                        >
                          {busyId === st.id ? 'Recording...' : 'Mark Paid'}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Completed Payments */}
          {trip.settlements.completed.length > 0 && (
            <section className="rounded-xl bg-white border border-[#E9E2E4] overflow-hidden">
              <div className="px-5 py-4 border-b border-[#EFE9EB]">
                <h2 className="font-display text-base font-semibold text-[#29252A]">
                  Completed Payments ({trip.settlements.completed.length})
                </h2>
              </div>

              <div className="divide-y divide-[#EFE9EB]">
                {trip.settlements.completed.map((st) => (
                  <div
                    key={st.id}
                    className="px-5 py-4 flex flex-wrap items-center justify-between gap-4"
                  >
                    <div className="flex items-center gap-2.5">
                      <CheckCircle2 className="h-4 w-4 text-[#2F6F4E] shrink-0" />
                      <span className="text-sm font-medium text-[#29252A]">
                        {st.from_member_name} paid {st.to_member_name}
                      </span>
                    </div>

                    <div className="flex items-center gap-4 shrink-0">
                      <span className="font-mono text-sm font-semibold tabular-nums text-[#2F6F4E]">
                        {formatINR(st.amount_paise)}
                      </span>
                      {!isCompleted && (
                        <button
                          type="button"
                          disabled={busyId === st.id}
                          onClick={async () => {
                            setBusyId(st.id);
                            try {
                              await onRevertSettlement(st.id);
                            } finally {
                              setBusyId(null);
                            }
                          }}
                          className="rounded-lg border border-[#DDD4D7] bg-white px-3 py-1.5 text-xs font-medium text-[#524A4E] hover:text-[#641C32] whitespace-nowrap"
                        >
                          Mark Unpaid
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      )}

      {/* TAB 3: ANALYTICS ONLY */}
      {activeTab === 'analytics' && (
        <div className="space-y-6">
          <section className="rounded-xl bg-white border border-[#E9E2E4] grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-[#EFE9EB]">
            <div className="p-5">
              <div className="text-xs font-medium text-[#524A4E]">
                Highest Spending Category
              </div>
              <div className="mt-2 font-display text-lg font-bold text-[#29252A]">
                {trip.analytics.highest_category
                  ? `${trip.analytics.highest_category.category} (${trip.analytics.highest_category.percentage}%)`
                  : 'N/A'}
              </div>
            </div>

            <div className="p-5">
              <div className="text-xs font-medium text-[#524A4E]">
                Most Frequent Payer
              </div>
              <div className="mt-2 font-display text-lg font-bold text-[#29252A]">
                {trip.analytics.most_frequent_payer
                  ? trip.analytics.most_frequent_payer.member_name
                  : 'N/A'}
              </div>
            </div>

            <div className="p-5">
              <div className="text-xs font-medium text-[#524A4E]">
                Average Expense
              </div>
              <div className="mt-2 font-mono text-lg font-bold tabular-nums text-[#29252A]">
                {formatINR(trip.analytics.average_expense_paise)}
              </div>
            </div>
          </section>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <section className="lg:col-span-5 rounded-xl bg-white border border-[#E9E2E4] p-5">
              <h3 className="font-display text-base font-semibold text-[#29252A] mb-4">
                Category Distribution
              </h3>

              {categoryChartData.length === 0 ? (
                <div className="py-12 text-center text-sm text-[#524A4E]">
                  No category data yet.
                </div>
              ) : (
                <>
                  <div className="h-56 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={categoryChartData}
                          dataKey="amountRupees"
                          nameKey="category"
                          innerRadius={54}
                          outerRadius={84}
                          paddingAngle={2}
                        >
                          {categoryChartData.map((entry) => (
                            <Cell key={entry.category} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip
                          formatter={(val: unknown) =>
                            formatINR(Math.round(Number(val || 0) * 100))
                          }
                          contentStyle={{
                            borderRadius: '8px',
                            border: '1px solid #E9E2E4',
                            fontSize: '12px',
                          }}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="mt-3 space-y-2 border-t border-[#EFE9EB] pt-3">
                    {categoryChartData.map((cat) => (
                      <div
                        key={cat.category}
                        className="flex items-center justify-between text-xs"
                      >
                        <span className="flex items-center gap-2 text-[#29252A]">
                          <span
                            className="inline-block h-2.5 w-2.5 rounded-sm"
                            style={{ backgroundColor: cat.color }}
                          />
                          <span>{cat.category}</span>
                        </span>
                        <span className="font-mono tabular-nums text-[#29252A]">
                          {formatINR(cat.amount_paise)}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </section>

            <section className="lg:col-span-7 rounded-xl bg-white border border-[#E9E2E4] p-5">
              <h3 className="font-display text-base font-semibold text-[#29252A] mb-4">
                Paid vs Assigned Share
              </h3>
              {balanceChartData.length === 0 ? (
                <div className="py-12 text-center text-sm text-[#524A4E]">
                  No member contribution data yet.
                </div>
              ) : (
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={balanceChartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#EFE9EB" vertical={false} />
                      <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#29252A' }} axisLine={{ stroke: '#E9E2E4' }} tickLine={false} />
                      <YAxis tick={{ fontSize: 11, fill: '#6E656B' }} tickFormatter={(v) => `₹${Math.round(Number(v) / 1000)}k`} axisLine={false} tickLine={false} />
                      <Tooltip
                        formatter={(val: unknown, name: unknown) => [
                          formatINR(Math.round(Number(val || 0) * 100)),
                          name === 'paidRupees' ? 'Total Paid' : 'Assigned Share',
                        ]}
                        contentStyle={{ borderRadius: '8px', border: '1px solid #E9E2E4', fontSize: '12px' }}
                      />
                      <Bar dataKey="paidRupees" name="paidRupees" fill="#3D9A9B" radius={[6, 6, 0, 0]} />
                      <Bar dataKey="shareRupees" name="shareRupees" fill="#8E7CC3" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </section>
          </div>

          {dailyChartData.length > 0 && (
            <section className="rounded-xl bg-white border border-[#E9E2E4] p-5">
              <h3 className="font-display text-base font-semibold text-[#29252A] mb-4">
                Daily Spending Timeline
              </h3>
              <div className="h-56 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={dailyChartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#EFE9EB" vertical={false} />
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#6E656B' }} axisLine={{ stroke: '#E9E2E4' }} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#6E656B' }} tickFormatter={(v) => `₹${Math.round(Number(v) / 1000)}k`} axisLine={false} tickLine={false} />
                    <Tooltip
                      formatter={(val: unknown) => [
                        formatINR(Math.round(Number(val || 0) * 100)),
                        'Daily Spend',
                      ]}
                      contentStyle={{ borderRadius: '8px', border: '1px solid #E9E2E4', fontSize: '12px' }}
                    />
                    <Area type="monotone" dataKey="amountRupees" stroke="#641C32" strokeWidth={2} fill="#F3E7EB" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </section>
          )}
        </div>
      )}

      {/* TAB 4: MEMBERS & SETTINGS */}
      {activeTab === 'members' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <section className="lg:col-span-7 rounded-xl bg-white border border-[#E9E2E4] overflow-hidden flex flex-col">
            <div className="px-5 py-4 border-b border-[#EFE9EB]">
              <h2 className="font-display text-base font-semibold text-[#29252A]">
                Trip Members
              </h2>
            </div>

            {memberError && (
              <div className="mx-5 mt-4 rounded-lg bg-[#F3E7EB] border border-[#B9788B] px-3.5 py-2.5 text-xs text-[#641C32]">
                {memberError}
              </div>
            )}

            <div className="divide-y divide-[#EFE9EB]">
              {trip.members.map((m) => (
                <div
                  key={m.id}
                  className="px-5 py-3 flex items-center justify-between gap-3"
                >
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-[#29252A] truncate">
                      {m.name}
                    </div>
                    <div className="text-xs text-[#6E656B] truncate">{m.email}</div>
                  </div>
                  {!isCompleted && (
                    <button
                      type="button"
                      disabled={busyId === m.id}
                      onClick={() => handleRemoveMemberClick(m.id)}
                      aria-label={`Remove ${m.name}`}
                      className="p-1.5 rounded-lg text-[#8E8489] hover:text-[#641C32] hover:bg-[#FAF9F7] disabled:opacity-40"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              ))}
            </div>

            {!isCompleted && (
              <form
                onSubmit={handleAddMemberSubmit}
                className="mt-auto p-4 bg-[#FAF9F7] border-t border-[#EFE9EB] flex flex-wrap sm:flex-nowrap items-center gap-2"
              >
                <input
                  type="text"
                  value={newMemberName}
                  onChange={(e) => setNewMemberName(e.target.value)}
                  placeholder="Member name"
                  className="flex-1 min-w-[120px] rounded-lg border border-[#DDD4D7] bg-white px-3 py-2 text-xs text-[#29252A] focus:border-[#641C32] focus:outline-none"
                />
                <input
                  type="email"
                  value={newMemberEmail}
                  onChange={(e) => setNewMemberEmail(e.target.value)}
                  placeholder="Email address"
                  className="flex-1 min-w-[150px] rounded-lg border border-[#DDD4D7] bg-white px-3 py-2 text-xs text-[#29252A] focus:border-[#641C32] focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={addingMember}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[#641C32] px-3 py-2 text-xs font-medium text-white hover:bg-[#873B52] disabled:opacity-60 whitespace-nowrap"
                >
                  <UserPlus className="h-3.5 w-3.5" />
                  <span>{addingMember ? 'Adding...' : 'Add'}</span>
                </button>
              </form>
            )}
          </section>

          <div className="lg:col-span-5 space-y-6">
            {!isCompleted && (
              <section className="rounded-xl bg-white border border-[#E9E2E4] p-5 flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-[#29252A]">Trip Details</h3>
                  <div className="text-xs text-[#6E656B] mt-0.5">
                    {trip.name} · {formatDateShort(trip.start_date)}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={onEditTrip}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-[#DDD4D7] bg-white px-3.5 py-2 text-xs font-medium text-[#29252A] hover:bg-[#FAF9F7] whitespace-nowrap"
                >
                  <Edit3 className="h-3.5 w-3.5" />
                  <span>Edit</span>
                </button>
              </section>
            )}

            {trip.email_deliveries.length > 0 && (
              <section className="rounded-xl bg-white border border-[#E9E2E4] p-5 flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-[#29252A]">
                  Member HTML Statements ({trip.email_deliveries.length})
                </h3>
                <button
                  type="button"
                  onClick={onOpenEmails}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-[#641C32] px-3.5 py-2 text-xs font-medium text-white hover:bg-[#873B52] whitespace-nowrap"
                >
                  <Mail className="h-3.5 w-3.5" />
                  <span>Open &amp; Download</span>
                </button>
              </section>
            )}

            <section className="rounded-xl bg-white border border-[#E9E2E4] p-5 flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-[#29252A]">Delete Trip</h3>
              {!confirmDeleteTrip ? (
                <button
                  type="button"
                  onClick={() => setConfirmDeleteTrip(true)}
                  className="rounded-lg border border-[#DDD4D7] px-3.5 py-1.5 text-xs font-medium text-[#641C32] hover:bg-[#F3E7EB] whitespace-nowrap"
                >
                  Delete Trip
                </button>
              ) : (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setConfirmDeleteTrip(false)}
                    className="rounded-lg border border-[#DDD4D7] px-3 py-1.5 text-xs font-medium text-[#524A4E]"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={onDeleteTrip}
                    className="rounded-lg bg-[#641C32] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#873B52]"
                  >
                    Confirm
                  </button>
                </div>
              )}
            </section>
          </div>
        </div>
      )}
    </div>
  );
}
