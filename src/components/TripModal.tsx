import { useState, type FormEvent } from 'react';
import { Plus, Trash2, X } from 'lucide-react';
import type { TripSummary } from '../types';

interface MemberDraft {
  name: string;
  email: string;
}

interface TripModalProps {
  isOpen: boolean;
  editingTrip?: TripSummary | null;
  onClose: () => void;
  onSubmitCreate: (payload: {
    name: string;
    start_date: string;
    members: MemberDraft[];
  }) => Promise<void>;
  onSubmitEdit?: (
    tripId: number,
    payload: {
      name: string;
      start_date: string;
    }
  ) => Promise<void>;
}

export function TripModal({
  isOpen,
  editingTrip,
  onClose,
  onSubmitCreate,
  onSubmitEdit,
}: TripModalProps) {
  const isEdit = Boolean(editingTrip);
  const today = new Date().toISOString().slice(0, 10);

  const [name, setName] = useState(editingTrip?.name || '');
  const [startDate, setStartDate] = useState(editingTrip?.start_date || today);
  const [members, setMembers] = useState<MemberDraft[]>([
    { name: '', email: '' },
    { name: '', email: '' },
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleAddMemberRow = () => {
    setMembers((prev) => [...prev, { name: '', email: '' }]);
  };

  const handleRemoveMemberRow = (idx: number) => {
    if (members.length <= 2) return;
    setMembers((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleMemberChange = (idx: number, field: keyof MemberDraft, value: string) => {
    setMembers((prev) =>
      prev.map((m, i) => (i === idx ? { ...m, [field]: value } : m))
    );
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError('Trip name or destination is required.');
      return;
    }

    if (!isEdit) {
      const cleaned = members.map((m) => ({
        name: m.name.trim(),
        email: m.email.trim(),
      }));
      if (cleaned.length < 2) {
        setError('Add at least 2 trip members.');
        return;
      }
      for (const m of cleaned) {
        if (!m.name || !m.email || !m.email.includes('@')) {
          setError('Every member requires a valid name and email address.');
          return;
        }
      }
      const emails = cleaned.map((m) => m.email.toLowerCase());
      if (new Set(emails).size !== emails.length) {
        setError('Each member must have a unique email address.');
        return;
      }

      setSubmitting(true);
      try {
        await onSubmitCreate({
          name: name.trim(),
          start_date: startDate,
          members: cleaned,
        });
        onClose();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to create trip.');
      } finally {
        setSubmitting(false);
      }
    } else if (editingTrip && onSubmitEdit) {
      setSubmitting(true);
      try {
        await onSubmitEdit(editingTrip.id, {
          name: name.trim(),
          start_date: startDate,
        });
        onClose();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update trip.');
      } finally {
        setSubmitting(false);
      }
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#29252A]/45">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="trip-modal-title"
        className="w-full max-w-xl max-h-[90vh] flex flex-col rounded-xl bg-white border border-[#E9E2E4] shadow-xl"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#EFE9EB]">
          <h2 id="trip-modal-title" className="font-display text-lg font-semibold text-[#29252A]">
            {isEdit ? 'Edit Trip' : 'Create New Trip'}
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
                Trip Name / Destination
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Goa Retreat"
                className="w-full rounded-lg border border-[#DDD4D7] bg-white px-3.5 py-2.5 text-sm text-[#29252A] focus:border-[#641C32] focus:outline-none focus:ring-2 focus:ring-[#F3E7EB]"
              />
            </div>

            <div className="sm:col-span-5">
              <label className="block text-xs font-medium text-[#524A4E] mb-1.5">
                Trip Date
              </label>
              <input
                type="date"
                required
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full rounded-lg border border-[#DDD4D7] bg-white px-3.5 py-2.5 text-sm font-mono text-[#29252A] focus:border-[#641C32] focus:outline-none focus:ring-2 focus:ring-[#F3E7EB]"
              />
            </div>
          </div>

          {!isEdit && (
            <div className="pt-2 border-t border-[#EFE9EB]">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-[#29252A]">Trip Members</h3>
                <button
                  type="button"
                  onClick={handleAddMemberRow}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-[#DDD4D7] bg-white px-3 py-1.5 text-xs font-medium text-[#641C32] hover:bg-[#F3E7EB] transition-colors whitespace-nowrap"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>Add Member</span>
                </button>
              </div>

              <div className="space-y-2.5">
                {members.map((m, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <input
                      type="text"
                      required
                      value={m.name}
                      onChange={(e) => handleMemberChange(idx, 'name', e.target.value)}
                      placeholder={`Member ${idx + 1} name`}
                      className="flex-1 min-w-0 rounded-lg border border-[#DDD4D7] bg-white px-3 py-2 text-sm text-[#29252A] focus:border-[#641C32] focus:outline-none"
                    />
                    <input
                      type="email"
                      required
                      value={m.email}
                      onChange={(e) => handleMemberChange(idx, 'email', e.target.value)}
                      placeholder="Email address"
                      className="flex-1 min-w-0 rounded-lg border border-[#DDD4D7] bg-white px-3 py-2 text-sm text-[#29252A] focus:border-[#641C32] focus:outline-none"
                    />
                    <button
                      type="button"
                      disabled={members.length <= 2}
                      onClick={() => handleRemoveMemberRow(idx)}
                      aria-label="Remove member row"
                      className="p-2 rounded-lg text-[#6E656B] hover:text-[#641C32] hover:bg-[#FAF9F7] disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

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
              {submitting ? 'Saving...' : isEdit ? 'Save Changes' : 'Create Trip'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
