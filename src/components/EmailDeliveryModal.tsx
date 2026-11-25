import { useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Download,
  ExternalLink,
  Mail,
  Maximize2,
  Minimize2,
  RefreshCw,
  X,
} from 'lucide-react';
import { api } from '../api/client';
import type { EmailDelivery, EmailProviderStatus } from '../types';

interface EmailDeliveryModalProps {
  isOpen: boolean;
  tripId: number;
  tripName: string;
  deliveries: EmailDelivery[];
  emailProvider: EmailProviderStatus;
  onClose: () => void;
  onResendSuccess: (updated: EmailDelivery) => void;
}

export function EmailDeliveryModal({
  isOpen,
  tripId,
  tripName,
  deliveries,
  emailProvider,
  onClose,
  onResendSuccess,
}: EmailDeliveryModalProps) {
  const [selectedId, setSelectedId] = useState<number>(deliveries[0]?.id || 0);
  const [resendingId, setResendingId] = useState<number | null>(null);
  const [expandedPreview, setExpandedPreview] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const activeDelivery =
    deliveries.find((d) => d.id === selectedId) || deliveries[0] || null;

  const handleResend = async (deliveryId: number) => {
    setError(null);
    setResendingId(deliveryId);
    try {
      const updated = await api.resendEmail(tripId, deliveryId);
      onResendSuccess(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to retry email delivery.');
    } finally {
      setResendingId(null);
    }
  };

  const handleDownloadBlob = (delivery: EmailDelivery) => {
    const blob = new Blob([delivery.html_body], {
      type: 'text/html;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const safeName =
      delivery.recipient_name.trim().replace(/[^a-zA-Z0-9_-]+/g, '_') || 'member';
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `tripledger_${safeName}.html`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#29252A]/45">
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-5xl h-[90vh] flex flex-col rounded-xl bg-white border border-[#E9E2E4] shadow-xl overflow-hidden"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#EFE9EB] shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <h2 className="font-display text-lg font-semibold text-[#29252A] truncate">
              {tripName} Statements
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="p-1.5 rounded-lg text-[#6E656B] hover:text-[#29252A] hover:bg-[#FAF9F7]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {!emailProvider.configured && (
          <div className="px-6 py-2.5 bg-[#F3E7EB] border-b border-[#DFC8D0] flex items-center gap-2 text-xs text-[#641C32] shrink-0">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>
              Demo Mode: No email credentials configured. Preview, open, or download each member statement below.
            </span>
          </div>
        )}

        {error && (
          <div className="px-6 py-2.5 bg-[#FAF9F7] border-b border-[#E9E2E4] text-xs text-[#641C32] shrink-0">
            {error}
          </div>
        )}

        <div className="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-12">
          {!expandedPreview && (
            <div className="md:col-span-4 border-b md:border-b-0 md:border-r border-[#EFE9EB] overflow-y-auto divide-y divide-[#EFE9EB]">
              {deliveries.map((d) => {
                const isSelected = activeDelivery?.id === d.id;
                return (
                  <button
                    key={d.id}
                    type="button"
                    onClick={() => setSelectedId(d.id)}
                    className={`w-full text-left px-4 py-3.5 transition-colors ${
                      isSelected ? 'bg-[#F3E7EB]/60' : 'bg-white hover:bg-[#FAF9F7]'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-[#29252A] truncate">
                        {d.recipient_name}
                      </span>
                      <span
                        className={`inline-flex items-center gap-1 text-xs font-medium shrink-0 ${
                          d.status === 'sent'
                            ? 'text-[#2F6F4E]'
                            : d.status === 'failed'
                            ? 'text-[#641C32]'
                            : 'text-[#873B52]'
                        }`}
                      >
                        {d.status === 'sent' ? (
                          <CheckCircle2 className="h-3.5 w-3.5" />
                        ) : d.status === 'failed' ? (
                          <AlertCircle className="h-3.5 w-3.5" />
                        ) : (
                          <Mail className="h-3.5 w-3.5" />
                        )}
                        <span>
                          {d.status === 'sent'
                            ? 'Sent'
                            : d.status === 'failed'
                            ? 'Failed'
                            : 'Demo'}
                        </span>
                      </span>
                    </div>
                    <div className="mt-0.5 text-xs text-[#6E656B] truncate">
                      {d.recipient_email}
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          <div
            className={`${
              expandedPreview ? 'md:col-span-12' : 'md:col-span-8'
            } flex flex-col min-h-0 bg-[#FAF9F7]`}
          >
            {activeDelivery ? (
              <>
                <div className="flex flex-wrap items-center justify-between gap-2 px-5 py-3 bg-white border-b border-[#EFE9EB] shrink-0">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-[#29252A] truncate">
                        {activeDelivery.recipient_name}
                      </span>
                      <span
                        className={`text-[11px] font-semibold ${
                          activeDelivery.status === 'sent'
                            ? 'text-[#2F6F4E]'
                            : activeDelivery.status === 'failed'
                            ? 'text-[#641C32]'
                            : 'text-[#873B52]'
                        }`}
                      >
                        {activeDelivery.status === 'sent'
                          ? `Sent via ${activeDelivery.provider.toUpperCase()}`
                          : activeDelivery.status === 'failed'
                          ? `Failed (${activeDelivery.provider.toUpperCase()})`
                          : 'Demo Preview'}
                      </span>
                    </div>
                    <div className="text-xs text-[#6E656B] truncate">
                      {activeDelivery.recipient_email}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => setExpandedPreview((prev) => !prev)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-[#DDD4D7] bg-white px-3 py-1.5 text-xs font-medium text-[#29252A] hover:bg-[#FAF9F7] whitespace-nowrap"
                    >
                      {expandedPreview ? (
                        <>
                          <Minimize2 className="h-3.5 w-3.5" />
                          <span>Show List</span>
                        </>
                      ) : (
                        <>
                          <Maximize2 className="h-3.5 w-3.5" />
                          <span>Expand</span>
                        </>
                      )}
                    </button>
                    <a
                      href={api.getViewEmailUrl(tripId, activeDelivery.id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 rounded-lg border border-[#DDD4D7] bg-white px-3 py-1.5 text-xs font-medium text-[#29252A] hover:bg-[#FAF9F7] whitespace-nowrap"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                      <span>Open HTML</span>
                    </a>
                    <button
                      type="button"
                      onClick={() => handleDownloadBlob(activeDelivery)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-[#DDD4D7] bg-white px-3 py-1.5 text-xs font-medium text-[#29252A] hover:bg-[#FAF9F7] whitespace-nowrap"
                    >
                      <Download className="h-3.5 w-3.5" />
                      <span>Download</span>
                    </button>
                    {emailProvider.configured && (
                      <button
                        type="button"
                        disabled={resendingId === activeDelivery.id}
                        onClick={() => handleResend(activeDelivery.id)}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-[#641C32] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#873B52] disabled:opacity-60 whitespace-nowrap"
                      >
                        <RefreshCw
                          className={`h-3.5 w-3.5 ${
                            resendingId === activeDelivery.id ? 'animate-spin' : ''
                          }`}
                        />
                        <span>Resend</span>
                      </button>
                    )}
                  </div>
                </div>
                {activeDelivery.status === 'failed' && activeDelivery.error_message && (
                  <div className="px-5 py-2.5 bg-[#F3E7EB] border-b border-[#DFC8D0] text-xs text-[#641C32] shrink-0">
                    Delivery error: {activeDelivery.error_message}
                  </div>
                )}
                <div className="flex-1 min-h-[420px] p-4 overflow-hidden">
                  <iframe
                    title={`Email summary for ${activeDelivery.recipient_name}`}
                    sandbox=""
                    srcDoc={activeDelivery.html_body}
                    className="w-full h-full min-h-[400px] rounded-lg border border-[#E9E2E4] bg-white"
                  />
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-sm text-[#6E656B]">
                Select a member to inspect their personalized statement.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
