import { useCallback, useEffect, useState } from 'react';
import { api } from './api/client';
import { DashboardView } from './components/DashboardView';
import { EmailDeliveryModal } from './components/EmailDeliveryModal';
import { EndTripModal } from './components/EndTripModal';
import { ExpenseModal } from './components/ExpenseModal';
import { NotificationsView } from './components/NotificationsView';
import { Sidebar, type ActivePage } from './components/Sidebar';
import { TripDetailView } from './components/TripDetailView';
import { TripModal } from './components/TripModal';
import type {
  DashboardData,
  EmailDelivery,
  Expense,
  NotificationItem,
  SplitMethod,
  TripDetail,
} from './types';

export default function App() {
  const [activePage, setActivePage] = useState<ActivePage>('dashboard');
  const [selectedTripId, setSelectedTripId] = useState<number | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [tripDetail, setTripDetail] = useState<TripDetail | null>(null);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Modals
  const [tripModalOpen, setTripModalOpen] = useState(false);
  const [editingTrip, setEditingTrip] = useState<TripDetail | null>(null);
  const [expenseModalOpen, setExpenseModalOpen] = useState(false);
  const [editingExpense, setEditingExpense] = useState<Expense | null>(null);
  const [endTripModalMode, setEndTripModalMode] = useState<'end' | 'reopen' | null>(null);
  const [emailModalOpen, setEmailModalOpen] = useState(false);

  const refreshGlobalData = useCallback(async () => {
    const [dashData, notifData] = await Promise.all([
      api.getDashboard(),
      api.listNotifications(),
    ]);
    setDashboard(dashData);
    setNotifications(notifData.items);
    setUnreadCount(notifData.unread_count);
  }, []);

  const refreshSelectedTrip = useCallback(async (tripId: number) => {
    const detail = await api.getTrip(tripId);
    setTripDetail(detail);
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        await refreshGlobalData();
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : 'Unable to load TripLedger data.');
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [refreshGlobalData]);

  const handleSelectTrip = useCallback(
    async (tripId: number) => {
      setError(null);
      setSelectedTripId(tripId);
      setActivePage('trip');
      try {
        await refreshSelectedTrip(tripId);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load trip.');
      }
    },
    [refreshSelectedTrip]
  );

  const handleCreateTrip = async (payload: {
    name: string;
    start_date: string;
    members: { name: string; email: string }[];
  }) => {
    const created = await api.createTrip(payload);
    await refreshGlobalData();
    setTripDetail(created);
    setSelectedTripId(created.id);
    setActivePage('trip');
  };

  const handleEditTrip = async (
    tripId: number,
    payload: {
      name: string;
      start_date: string;
    }
  ) => {
    const updated = await api.updateTrip(tripId, payload);
    setTripDetail(updated);
    await refreshGlobalData();
  };

  const handleDeleteTrip = async () => {
    if (!tripDetail) return;
    await api.deleteTrip(tripDetail.id);
    setTripDetail(null);
    setSelectedTripId(null);
    setActivePage('dashboard');
    await refreshGlobalData();
  };

  const handleSaveExpense = async (payload: {
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
  }) => {
    if (!tripDetail) return;
    if (editingExpense) {
      await api.updateExpense(tripDetail.id, editingExpense.id, payload);
    } else {
      await api.createExpense(tripDetail.id, payload);
    }
    await Promise.all([refreshSelectedTrip(tripDetail.id), refreshGlobalData()]);
  };

  const handleDeleteExpense = async (expenseId: number) => {
    if (!tripDetail) return;
    await api.deleteExpense(tripDetail.id, expenseId);
    await Promise.all([refreshSelectedTrip(tripDetail.id), refreshGlobalData()]);
  };

  const handleAddMember = async (name: string, email: string) => {
    if (!tripDetail) return;
    await api.addMember(tripDetail.id, { name, email });
    await Promise.all([refreshSelectedTrip(tripDetail.id), refreshGlobalData()]);
  };

  const handleRemoveMember = async (memberId: number) => {
    if (!tripDetail) return;
    await api.removeMember(tripDetail.id, memberId);
    await Promise.all([refreshSelectedTrip(tripDetail.id), refreshGlobalData()]);
  };

  const handleCompleteSettlement = async (settlementId: number) => {
    if (!tripDetail) return;
    await api.completeSettlement(tripDetail.id, settlementId);
    await Promise.all([refreshSelectedTrip(tripDetail.id), refreshGlobalData()]);
  };

  const handleRevertSettlement = async (settlementId: number) => {
    if (!tripDetail) return;
    await api.revertSettlement(tripDetail.id, settlementId);
    await Promise.all([refreshSelectedTrip(tripDetail.id), refreshGlobalData()]);
  };

  const handleSendReminders = async () => {
    if (!tripDetail) return;
    await api.sendReminders(tripDetail.id);
    await refreshGlobalData();
  };

  const handleEndOrReopenConfirm = async () => {
    if (!tripDetail || !endTripModalMode) return;
    if (endTripModalMode === 'end') {
      const updated = await api.endTrip(tripDetail.id);
      setTripDetail(updated);
      await refreshGlobalData();
      setEmailModalOpen(true);
    } else {
      const updated = await api.reopenTrip(tripDetail.id);
      setTripDetail(updated);
      await refreshGlobalData();
    }
  };

  const handleEmailResendSuccess = (updatedDelivery: EmailDelivery) => {
    setTripDetail((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        email_deliveries: prev.email_deliveries.map((d) =>
          d.id === updatedDelivery.id ? updatedDelivery : d
        ),
      };
    });
  };

  const handleMarkNotificationRead = async (id: number) => {
    await api.markNotificationRead(id);
    await refreshGlobalData();
  };

  const handleMarkAllNotificationsRead = async () => {
    await api.markAllNotificationsRead();
    await refreshGlobalData();
  };

  return (
    <div className="min-h-screen bg-[#FAF9F7] text-[#29252A]">
      {activePage === 'dashboard' ? (
        <main className="min-w-0">
          {error && (
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-10 pt-4">
              <div className="rounded-xl bg-[#F3E7EB] border border-[#B9788B] px-4 py-3 text-sm text-[#641C32] flex items-center justify-between">
                <span>{error}</span>
                <button
                  type="button"
                  onClick={() => setError(null)}
                  className="text-xs font-semibold hover:underline"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}

          {loading && !dashboard ? (
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-10 py-14 space-y-6">
              <div className="h-10 w-64 rounded-lg bg-[#EFE9EB] animate-pulse" />
              <div className="h-72 rounded-xl bg-white border border-[#E9E2E4] animate-pulse" />
              <div className="h-80 rounded-xl bg-white border border-[#E9E2E4] animate-pulse" />
            </div>
          ) : dashboard ? (
            <DashboardView
              data={dashboard}
              unreadCount={unreadCount}
              onSelectTrip={handleSelectTrip}
              onNewTrip={() => {
                setEditingTrip(null);
                setTripModalOpen(true);
              }}
              onOpenNotifications={() => setActivePage('notifications')}
            />
          ) : null}
        </main>
      ) : (
        <div className="min-h-screen flex flex-col lg:flex-row">
          <Sidebar
            activePage={activePage}
            selectedTripId={selectedTripId}
            trips={dashboard?.trips || []}
            unreadCount={unreadCount}
            mobileOpen={mobileMenuOpen}
            onCloseMobile={() => setMobileMenuOpen(false)}
            onOpenMobile={() => setMobileMenuOpen(true)}
            onNavigateDashboard={() => {
              setActivePage('dashboard');
              setSelectedTripId(null);
            }}
            onNavigateNotifications={() => {
              setActivePage('notifications');
            }}
            onSelectTrip={handleSelectTrip}
            onNewTrip={() => {
              setEditingTrip(null);
              setTripModalOpen(true);
            }}
          />

          <main className="flex-1 min-w-0">
            {error && (
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6">
                <div className="rounded-xl bg-[#F3E7EB] border border-[#B9788B] px-4 py-3 text-sm text-[#641C32] flex items-center justify-between">
                  <span>{error}</span>
                  <button
                    type="button"
                    onClick={() => setError(null)}
                    className="text-xs font-semibold hover:underline"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            )}

            {activePage === 'notifications' ? (
              <NotificationsView
                items={notifications}
                unreadCount={unreadCount}
                onMarkRead={handleMarkNotificationRead}
                onMarkAllRead={handleMarkAllNotificationsRead}
                onOpenTrip={handleSelectTrip}
              />
            ) : activePage === 'trip' && tripDetail ? (
              <TripDetailView
                trip={tripDetail}
                onBack={() => {
                  setActivePage('dashboard');
                  setSelectedTripId(null);
                }}
                onEditTrip={() => {
                  setEditingTrip(tripDetail);
                  setTripModalOpen(true);
                }}
                onDeleteTrip={handleDeleteTrip}
                onAddExpense={() => {
                  setEditingExpense(null);
                  setExpenseModalOpen(true);
                }}
                onEditExpense={(exp) => {
                  setEditingExpense(exp);
                  setExpenseModalOpen(true);
                }}
                onDeleteExpense={handleDeleteExpense}
                onAddMember={handleAddMember}
                onRemoveMember={handleRemoveMember}
                onCompleteSettlement={handleCompleteSettlement}
                onRevertSettlement={handleRevertSettlement}
                onSendReminders={handleSendReminders}
                onOpenEndTrip={() => setEndTripModalMode('end')}
                onOpenReopenTrip={() => setEndTripModalMode('reopen')}
                onOpenEmails={() => setEmailModalOpen(true)}
              />
            ) : (
              <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 text-sm text-[#6E656B]">
                Loading trip details...
              </div>
            )}
          </main>
        </div>
      )}

      {tripModalOpen && (
        <TripModal
          isOpen={tripModalOpen}
          editingTrip={editingTrip}
          onClose={() => {
            setTripModalOpen(false);
            setEditingTrip(null);
          }}
          onSubmitCreate={handleCreateTrip}
          onSubmitEdit={handleEditTrip}
        />
      )}

      {expenseModalOpen && tripDetail && (
        <ExpenseModal
          isOpen={expenseModalOpen}
          tripStartDate={tripDetail.start_date}
          members={tripDetail.members}
          editingExpense={editingExpense}
          onClose={() => {
            setExpenseModalOpen(false);
            setEditingExpense(null);
          }}
          onSave={handleSaveExpense}
        />
      )}

      {endTripModalMode && tripDetail && (
        <EndTripModal
          isOpen={Boolean(endTripModalMode)}
          mode={endTripModalMode}
          trip={tripDetail}
          emailProvider={tripDetail.email_provider}
          onClose={() => setEndTripModalMode(null)}
          onConfirm={handleEndOrReopenConfirm}
        />
      )}

      {emailModalOpen && tripDetail && (
        <EmailDeliveryModal
          isOpen={emailModalOpen}
          tripId={tripDetail.id}
          tripName={tripDetail.name}
          deliveries={tripDetail.email_deliveries}
          emailProvider={tripDetail.email_provider}
          onClose={() => setEmailModalOpen(false)}
          onResendSuccess={handleEmailResendSuccess}
        />
      )}
    </div>
  );
}
