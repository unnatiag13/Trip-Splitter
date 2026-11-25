import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { X } from 'lucide-react';
import type { Expense, Member, SplitMethod } from '../types';
import {
  EXPENSE_CATEGORIES,
  formatINR,
  paiseToRupeeString,
  rupeeStringToPaise,
} from '../utils/format';

interface ExpenseModalProps {
  isOpen: boolean;
  tripStartDate: string;
  members: Member[];
  editingExpense: Expense | null;
  onClose: () => void;
  onSave: (payload: {
    title: string;
    amount_paise: number;
    category: string;
    expense_date: string;
    payer_id: number;
    split_method: SplitMethod;
    participants: {
      member_id: number;
      share_paise?: number;
      percentage_bps?: number;
    }[];
    notes: string | null;
  }) => Promise<void>;
}

export function ExpenseModal({
  isOpen,
  tripStartDate,
  members,
  editingExpense,
  onClose,
  onSave,
}: ExpenseModalProps) {
  const isEdit = Boolean(editingExpense);
  const masterCheckboxRef = useRef<HTMLInputElement | null>(null);

  const [title, setTitle] = useState('');
  const [amountInput, setAmountInput] = useState('');
  const [category, setCategory] = useState<string>('Food');
  const [expenseDate, setExpenseDate] = useState<string>(tripStartDate);
  const [payerId, setPayerId] = useState<number>(members[0]?.id || 0);
  const [splitMethod, setSplitMethod] = useState<SplitMethod>('equal');
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [customRupees, setCustomRupees] = useState<Record<number, string>>({});
  const [percentages, setPercentages] = useState<Record<number, string>>({});
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setError(null);
    if (editingExpense) {
      setTitle(editingExpense.title);
      setAmountInput(paiseToRupeeString(editingExpense.amount_paise));
      setCategory(editingExpense.category);
      setExpenseDate(editingExpense.expense_date);
      setPayerId(editingExpense.payer_id);
      setSplitMethod(editingExpense.split_method);
      const pIds = editingExpense.shares.map((s) => s.member_id);
      setSelectedIds(pIds);

      const cMap: Record<number, string> = {};
      const pctMap: Record<number, string> = {};
      for (const m of members) {
        const share = editingExpense.shares.find((s) => s.member_id === m.id);
        cMap[m.id] = share ? paiseToRupeeString(share.share_paise) : '0.00';
        pctMap[m.id] =
          share && share.percentage_bps !== null
            ? (share.percentage_bps / 100).toFixed(2)
            : '0.00';
      }
      setCustomRupees(cMap);
      setPercentages(pctMap);
      setNotes(editingExpense.notes || '');
    } else {
      setTitle('');
      setAmountInput('');
      setCategory('Food');
      setExpenseDate(tripStartDate || new Date().toISOString().slice(0, 10));
      setPayerId(members[0]?.id || 0);
      setSplitMethod('equal');
      const allIds = members.map((m) => m.id);
      setSelectedIds(allIds);
      const cMap: Record<number, string> = {};
      const pctMap: Record<number, string> = {};
      const eqPct = members.length > 0 ? (100 / members.length).toFixed(2) : '0.00';
      for (const m of members) {
        cMap[m.id] = '0.00';
        pctMap[m.id] = eqPct;
      }
      setCustomRupees(cMap);
      setPercentages(pctMap);
      setNotes('');
    }
  }, [isOpen, editingExpense, members, tripStartDate]);

  const allSelected = members.length > 0 && selectedIds.length === members.length;
  const someSelected = selectedIds.length > 0 && selectedIds.length < members.length;

  useEffect(() => {
    if (masterCheckboxRef.current) {
      masterCheckboxRef.current.indeterminate = someSelected;
    }
  }, [someSelected]);

  const amountPaise = useMemo(() => rupeeStringToPaise(amountInput), [amountInput]);

  // Live preview shares in exact integer paise matching backend rounding
  const sharePreview = useMemo(() => {
    const map: Record<number, number> = {};
    const orderedSelected = members
      .map((m) => m.id)
      .filter((id) => selectedIds.includes(id));
    const n = orderedSelected.length;

    if (n === 0 || amountPaise <= 0) {
      return { map, customSumPaise: 0, totalBps: 0 };
    }

    if (splitMethod === 'equal') {
      const base = Math.floor(amountPaise / n);
      const rem = amountPaise % n;
      orderedSelected.forEach((id, idx) => {
        map[id] = base + (idx < rem ? 1 : 0);
      });
      return { map, customSumPaise: amountPaise, totalBps: 10000 };
    }

    if (splitMethod === 'custom') {
      let sum = 0;
      for (const id of orderedSelected) {
        const p = rupeeStringToPaise(customRupees[id] || '0');
        map[id] = p;
        sum += p;
      }
      return { map, customSumPaise: sum, totalBps: 10000 };
    }

    // percentage split using exact integer basis points + largest remainder
    const bpsList = orderedSelected.map((id) => {
      const val = Number.parseFloat(percentages[id] || '0');
      return Number.isFinite(val) && val >= 0 ? Math.round(val * 100) : 0;
    });
    const totalBps = bpsList.reduce((acc, v) => acc + v, 0);
    if (totalBps === 10000) {
      const exactNums = bpsList.map((bps) => amountPaise * bps);
      const baseShares = exactNums.map((num) => Math.floor(num / 10000));
      const remainders = exactNums
        .map((num, idx) => ({ rem: num % 10000, idx }))
        .sort((a, b) => (b.rem !== a.rem ? b.rem - a.rem : a.idx - b.idx));
      const leftover = amountPaise - baseShares.reduce((a, b) => a + b, 0);
      for (let i = 0; i < leftover; i++) {
        baseShares[remainders[i].idx] += 1;
      }
      orderedSelected.forEach((id, idx) => {
        map[id] = baseShares[idx];
      });
    } else {
      orderedSelected.forEach((id, idx) => {
        map[id] = Math.round((amountPaise * bpsList[idx]) / 10000);
      });
    }
    return { map, customSumPaise: amountPaise, totalBps };
  }, [amountPaise, customRupees, members, percentages, selectedIds, splitMethod]);

  if (!isOpen) return null;

  const toggleAll = () => {
    if (allSelected) {
      setSelectedIds([]);
    } else {
      setSelectedIds(members.map((m) => m.id));
    }
  };

  const toggleMember = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const distributePercentagesEqually = () => {
    const orderedSelected = members
      .map((m) => m.id)
      .filter((id) => selectedIds.includes(id));
    if (orderedSelected.length === 0) return;
    const n = orderedSelected.length;
    const baseBps = Math.floor(10000 / n);
    const rem = 10000 % n;
    const next: Record<number, string> = { ...percentages };
    orderedSelected.forEach((id, idx) => {
      const bps = baseBps + (idx < rem ? 1 : 0);
      next[id] = (bps / 100).toFixed(2);
    });
    setPercentages(next);
  };

  const distributeCustomEqually = () => {
    const orderedSelected = members
      .map((m) => m.id)
      .filter((id) => selectedIds.includes(id));
    if (orderedSelected.length === 0 || amountPaise <= 0) return;
    const n = orderedSelected.length;
    const base = Math.floor(amountPaise / n);
    const rem = amountPaise % n;
    const next: Record<number, string> = { ...customRupees };
    orderedSelected.forEach((id, idx) => {
      next[id] = paiseToRupeeString(base + (idx < rem ? 1 : 0));
    });
    setCustomRupees(next);
  };

  const payerName = members.find((m) => m.id === payerId)?.name || 'Selected member';
  const payerIncluded = selectedIds.includes(payerId);
  const isPersonal = selectedIds.length === 1 && payerIncluded;
  const customDiff = amountPaise - sharePreview.customSumPaise;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!title.trim()) {
      setError('Expense title is required.');
      return;
    }
    if (amountPaise <= 0) {
      setError('Amount must be greater than ₹0.00.');
      return;
    }
    if (!payerId) {
      setError('Please select who paid.');
      return;
    }
    if (selectedIds.length === 0) {
      setError('Select at least one participant.');
      return;
    }

    const orderedSelected = members
      .map((m) => m.id)
      .filter((id) => selectedIds.includes(id));

    if (splitMethod === 'custom' && customDiff !== 0) {
      setError(
        `Custom shares must equal ${formatINR(amountPaise)} (difference: ${formatINR(customDiff)}).`
      );
      return;
    }

    if (splitMethod === 'percentage' && sharePreview.totalBps !== 10000) {
      setError(
        `Percentages must total 100.00% (currently ${(sharePreview.totalBps / 100).toFixed(2)}%).`
      );
      return;
    }

    const participants = orderedSelected.map((id) => {
      if (splitMethod === 'custom') {
        return {
          member_id: id,
          share_paise: rupeeStringToPaise(customRupees[id] || '0'),
        };
      }
      if (splitMethod === 'percentage') {
        const val = Number.parseFloat(percentages[id] || '0');
        return {
          member_id: id,
          percentage_bps: Number.isFinite(val) ? Math.round(val * 100) : 0,
        };
      }
      return { member_id: id };
    });

    setSubmitting(true);
    try {
      await onSave({
        title: title.trim(),
        amount_paise: amountPaise,
        category,
        expense_date: expenseDate,
        payer_id: payerId,
        split_method: splitMethod,
        participants,
        notes: notes.trim() || null,
      });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save expense.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#29252A]/45">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="expense-modal-title"
        className="w-full max-w-2xl max-h-[92vh] flex flex-col rounded-xl bg-white border border-[#E9E2E4] shadow-xl"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#EFE9EB]">
          <h2 id="expense-modal-title" className="font-display text-lg font-semibold text-[#29252A]">
            {isEdit ? 'Edit Expense' : 'Add Expense'}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="p-1.5 rounded-lg text-[#6E656B] hover:text-[#29252A] hover:bg-[#FAF9F7]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="overflow-y-auto px-6 py-5 space-y-5">
          {error && (
            <div className="rounded-lg bg-[#F3E7EB] border border-[#B9788B] px-4 py-3 text-sm text-[#641C32]">
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-12 gap-4">
            <div className="sm:col-span-7">
              <label className="block text-xs font-medium text-[#524A4E] mb-1.5">
                Title / Description
              </label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Beachside Dinner"
                className="w-full rounded-lg border border-[#DDD4D7] bg-white px-3.5 py-2.5 text-sm text-[#29252A] focus:border-[#641C32] focus:outline-none focus:ring-2 focus:ring-[#F3E7EB]"
              />
            </div>

            <div className="sm:col-span-5">
              <label className="block text-xs font-medium text-[#524A4E] mb-1.5">
                Amount (₹)
              </label>
              <input
                type="number"
                required
                min="0.01"
                step="0.01"
                value={amountInput}
                onChange={(e) => setAmountInput(e.target.value)}
                placeholder="0.00"
                className="w-full rounded-lg border border-[#DDD4D7] bg-white px-3.5 py-2.5 text-sm font-mono tabular-nums text-[#29252A] focus:border-[#641C32] focus:outline-none focus:ring-2 focus:ring-[#F3E7EB]"
              />
            </div>

            <div className="sm:col-span-4">
              <label className="block text-xs font-medium text-[#524A4E] mb-1.5">
                Category
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full rounded-lg border border-[#DDD4D7] bg-white px-3 py-2.5 text-sm text-[#29252A] focus:border-[#641C32] focus:outline-none"
              >
                {EXPENSE_CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            <div className="sm:col-span-4">
              <label className="block text-xs font-medium text-[#524A4E] mb-1.5">
                Date
              </label>
              <input
                type="date"
                required
                value={expenseDate}
                onChange={(e) => setExpenseDate(e.target.value)}
                className="w-full rounded-lg border border-[#DDD4D7] bg-white px-3 py-2.5 text-sm font-mono text-[#29252A] focus:border-[#641C32] focus:outline-none"
              />
            </div>

            <div className="sm:col-span-4">
              <label className="block text-xs font-medium text-[#524A4E] mb-1.5">
                Paid By
              </label>
              <select
                value={payerId}
                onChange={(e) => setPayerId(Number(e.target.value))}
                className="w-full rounded-lg border border-[#DDD4D7] bg-white px-3 py-2.5 text-sm text-[#29252A] focus:border-[#641C32] focus:outline-none"
              >
                {members.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Split Method */}
          <div>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <span className="text-xs font-medium text-[#524A4E]">Split Method</span>
              {splitMethod === 'custom' && (
                <button
                  type="button"
                  onClick={distributeCustomEqually}
                  className="text-xs font-medium text-[#641C32] hover:underline"
                >
                  Fill Equally
                </button>
              )}
              {splitMethod === 'percentage' && (
                <button
                  type="button"
                  onClick={distributePercentagesEqually}
                  className="text-xs font-medium text-[#641C32] hover:underline"
                >
                  Distribute 100% Equally
                </button>
              )}
            </div>
            <div className="grid grid-cols-3 gap-1 p-1 rounded-lg bg-[#F3E7EB]/60 border border-[#E9E2E4]">
              {(['equal', 'custom', 'percentage'] as SplitMethod[]).map((method) => (
                <button
                  key={method}
                  type="button"
                  onClick={() => setSplitMethod(method)}
                  className={`py-2 px-3 rounded-md text-xs font-medium transition-colors whitespace-nowrap ${
                    splitMethod === method
                      ? 'bg-white text-[#641C32] shadow-sm'
                      : 'text-[#524A4E] hover:text-[#29252A]'
                  }`}
                >
                  {method === 'equal'
                    ? 'Equal Split'
                    : method === 'custom'
                    ? 'Custom Amounts'
                    : 'Percentage Split'}
                </button>
              ))}
            </div>
          </div>

          {/* Participant Selection */}
          <div className="rounded-xl border border-[#E9E2E4] overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-2 bg-[#FAF9F7] px-4 py-3 border-b border-[#E9E2E4]">
              <label className="inline-flex items-center gap-2.5 cursor-pointer select-none">
                <input
                  ref={masterCheckboxRef}
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleAll}
                  className="h-4 w-4 rounded border-[#B9788B] accent-[#641C32]"
                />
                <span className="text-xs font-semibold text-[#29252A]">
                  {allSelected ? 'Deselect All' : 'Select All'}
                </span>
              </label>

              <div className="text-xs text-[#6E656B] flex items-center gap-2">
                <span className="font-mono tabular-nums font-medium text-[#29252A]">
                  {selectedIds.length} of {members.length} selected
                </span>
                {selectedIds.length > 0 && !payerIncluded && (
                  <>
                    <span aria-hidden="true">·</span>
                    <span className="text-[#873B52]">Payer excluded</span>
                  </>
                )}
                {isPersonal && (
                  <>
                    <span aria-hidden="true">·</span>
                    <span className="text-[#873B52]">Personal expense ({payerName})</span>
                  </>
                )}
              </div>
            </div>

            <div className="divide-y divide-[#EFE9EB] max-h-64 overflow-y-auto">
              {members.map((m) => {
                const isChecked = selectedIds.includes(m.id);
                const computedShare = sharePreview.map[m.id] || 0;
                return (
                  <div
                    key={m.id}
                    className={`flex items-center justify-between gap-3 px-4 py-2.5 transition-colors ${
                      isChecked ? 'bg-white' : 'bg-[#FAF9F7]/60'
                    }`}
                  >
                    <label className="flex items-center gap-3 min-w-0 flex-1 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleMember(m.id)}
                        className="h-4 w-4 rounded border-[#B9788B] accent-[#641C32] shrink-0"
                      />
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-[#29252A] truncate">
                          {m.name}
                          {m.id === payerId && (
                            <span className="ml-2 text-xs font-normal text-[#873B52]">
                              (Payer)
                            </span>
                          )}
                        </div>
                      </div>
                    </label>

                    <div className="flex items-center gap-3 shrink-0">
                      {isChecked && splitMethod === 'custom' && (
                        <div className="flex items-center gap-1">
                          <span className="text-xs text-[#6E656B]">₹</span>
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={customRupees[m.id] ?? '0.00'}
                            onChange={(e) =>
                              setCustomRupees((prev) => ({ ...prev, [m.id]: e.target.value }))
                            }
                            aria-label={`Custom amount for ${m.name}`}
                            className="w-24 rounded-md border border-[#DDD4D7] px-2 py-1 text-right text-xs font-mono tabular-nums focus:border-[#641C32] focus:outline-none"
                          />
                        </div>
                      )}

                      {isChecked && splitMethod === 'percentage' && (
                        <div className="flex items-center gap-1">
                          <input
                            type="number"
                            min="0"
                            max="100"
                            step="0.01"
                            value={percentages[m.id] ?? '0.00'}
                            onChange={(e) =>
                              setPercentages((prev) => ({ ...prev, [m.id]: e.target.value }))
                            }
                            aria-label={`Percentage for ${m.name}`}
                            className="w-20 rounded-md border border-[#DDD4D7] px-2 py-1 text-right text-xs font-mono tabular-nums focus:border-[#641C32] focus:outline-none"
                          />
                          <span className="text-xs text-[#6E656B]">%</span>
                        </div>
                      )}

                      <div className="w-24 text-right font-mono text-xs font-semibold tabular-nums text-[#29252A]">
                        {isChecked ? formatINR(computedShare) : '₹0.00'}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {splitMethod === 'custom' && selectedIds.length > 0 && (
              <div className="flex items-center justify-between px-4 py-2.5 bg-[#FAF9F7] border-t border-[#E9E2E4] text-xs">
                <span className="text-[#524A4E]">
                  Allocated: <span className="font-mono font-medium">{formatINR(sharePreview.customSumPaise)}</span> of{' '}
                  <span className="font-mono font-medium">{formatINR(amountPaise)}</span>
                </span>
                <span
                  className={`font-mono font-semibold tabular-nums ${
                    customDiff === 0 ? 'text-[#2F6F4E]' : 'text-[#641C32]'
                  }`}
                >
                  {customDiff === 0
                    ? 'Exact match'
                    : customDiff > 0
                    ? `${formatINR(customDiff)} remaining`
                    : `${formatINR(Math.abs(customDiff))} over`}
                </span>
              </div>
            )}

            {splitMethod === 'percentage' && selectedIds.length > 0 && (
              <div className="flex items-center justify-between px-4 py-2.5 bg-[#FAF9F7] border-t border-[#E9E2E4] text-xs">
                <span className="text-[#524A4E]">Total Percentage</span>
                <span
                  className={`font-mono font-semibold tabular-nums ${
                    sharePreview.totalBps === 10000 ? 'text-[#2F6F4E]' : 'text-[#641C32]'
                  }`}
                >
                  {(sharePreview.totalBps / 100).toFixed(2)}% / 100.00%
                </span>
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-[#524A4E] mb-1.5">
              Notes (Optional)
            </label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional context about this split"
              className="w-full rounded-lg border border-[#DDD4D7] bg-white px-3.5 py-2 text-sm text-[#29252A] focus:border-[#641C32] focus:outline-none"
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#EFE9EB]">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-[#DDD4D7] bg-white px-4 py-2 text-sm font-medium text-[#524A4E] hover:bg-[#FAF9F7] whitespace-nowrap"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-[#641C32] px-5 py-2 text-sm font-medium text-white hover:bg-[#873B52] disabled:opacity-60 whitespace-nowrap"
            >
              {submitting ? 'Saving...' : isEdit ? 'Update Expense' : 'Save Expense'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
