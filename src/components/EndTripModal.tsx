import { useState } from 'react';
import { Lock, RotateCcw, X } from 'lucide-react';
import type { EmailProviderStatus, TripDetail } from '../types';
import { formatINR } from '../utils/format';

interface EndTripModalProps {
  isOpen: boolean;
  mode: 'end' | 'reopen';
  trip: TripDetail;
  emailProvider: EmailProviderStatus;
  onClose: () => void;
  onConfirm: () => Promise<void>;
}

export function EndTripModal({
  isOpen,
  mode,
  trip,
  emailProvider,
  onClose,
  onConfirm,
}: EndTripModalProps) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const isEnd = mode === 'end';

  const handleConfirm = async () => {
    setError(null);
    setSubmitting(true);
    try {
      await onConfirm();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Action failed.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#29252A]/45">
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-xl bg-white border border-[#E9E2E4] shadow-xl overflow-hidden"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#EFE9EB]">
          <div className="flex items-center gap-2.5">
            {isEnd ? (
              <Lock className="h-4 w-4 text-[#641C32]" />
            ) : (
              <RotateCcw className="h-4 w-4 text-[#641C32]" />
            )}
            <h2 className="font-display text-base font-semibold text-[#29252A]">
              {isEnd ? 'End Trip & Send Summaries' : 'Reopen Completed Trip'}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close confirmation"
            className="p-1.5 rounded-lg text-[#6E656B] hover:text-[#29252A]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-4 text-sm text-[#524A4E]">
          {error && (
            <div className="rounded-lg bg-[#F3E7EB] border border-[#B9788B] px-3.5 py-2.5 text-xs text-[#641C32]">
              {error}
            </div>
          )}

          {isEnd ? (
            <>
              <p className="leading-relaxed">
                Ending <strong className="text-[#29252A]">{trip.name}</strong> will recalculate all consolidated balances and lock the trip as Completed (read-only).
              </p>
              <div className="rounded-lg bg-[#FAF9F7] border border-[#E9E2E4] p-3.5 space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span>Members receiving statements</span>
                  <span className="font-mono font-semibold text-[#29252A]">{trip.members.length}</span>
                </div>
                <div className="flex justify-between">
                  <span>Total trip expenditure</span>
                  <span className="font-mono font-semibold text-[#29252A]">
                    {formatINR(trip.total_spend_paise)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Pending suggested settlements</span>
                  <span className="font-mono font-semibold text-[#641C32]">
                    {trip.settlements.suggested.length} ({formatINR(trip.pending_settlement_paise)})
                  </span>
                </div>
              </div>
              <p className="text-xs text-[#6E656B] leading-relaxed">
                Pending settlements will remain marked as suggested, never auto-completed.{' '}
                {emailProvider.configured
                  ? `Emails will be sent via ${emailProvider.provider.toUpperCase()}.`
                  : 'Email credentials are unavailable, so Demo Mode will generate downloadable HTML summaries for each member.'}
              </p>
            </>
          ) : (
            <p className="leading-relaxed">
              Reopening <strong className="text-[#29252A]">{trip.name}</strong> will restore editing for expenses, members, and settlement completion status. Previously generated email records remain preserved.
            </p>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 px-6 py-4 bg-[#FAF9F7] border-t border-[#EFE9EB]">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-[#DDD4D7] bg-white px-4 py-2 text-sm font-medium text-[#524A4E] hover:bg-[#FAF9F7] whitespace-nowrap"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={submitting}
            onClick={handleConfirm}
            className="rounded-lg bg-[#641C32] px-4 py-2 text-sm font-medium text-white hover:bg-[#873B52] disabled:opacity-60 whitespace-nowrap"
          >
            {submitting
              ? 'Processing...'
              : isEnd
              ? 'Confirm & End Trip'
              : 'Confirm Reopen'}
          </button>
        </div>
      </div>
    </div>
  );
}
