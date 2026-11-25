import {
  Bell,
  LayoutDashboard,
  MapPin,
  Menu,
  Plus,
  X,
} from 'lucide-react';
import type { TripSummary } from '../types';

export type ActivePage = 'dashboard' | 'trip' | 'notifications';

interface SidebarProps {
  activePage: ActivePage;
  selectedTripId: number | null;
  trips: TripSummary[];
  unreadCount: number;
  mobileOpen: boolean;
  onCloseMobile: () => void;
  onOpenMobile: () => void;
  onNavigateDashboard: () => void;
  onNavigateNotifications: () => void;
  onSelectTrip: (tripId: number) => void;
  onNewTrip: () => void;
}

export function Sidebar({
  activePage,
  selectedTripId,
  trips,
  unreadCount,
  mobileOpen,
  onCloseMobile,
  onOpenMobile,
  onNavigateDashboard,
  onNavigateNotifications,
  onSelectTrip,
  onNewTrip,
}: SidebarProps) {
  const activeTrips = trips.filter((t) => t.status === 'active');
  const completedTrips = trips.filter((t) => t.status === 'completed');

  const navContent = (
    <div className="flex h-full flex-col bg-white border-r border-[#E9E2E4]">
      <div className="flex items-center justify-between px-5 py-5 border-b border-[#EFE9EB]">
        <button
          type="button"
          onClick={() => {
            onNavigateDashboard();
            onCloseMobile();
          }}
          className="font-display text-lg font-bold tracking-tight text-[#641C32] whitespace-nowrap focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#641C32] rounded"
        >
          TripLedger
        </button>
        <button
          type="button"
          onClick={onCloseMobile}
          aria-label="Close navigation"
          className="lg:hidden p-1.5 text-[#524A4E] hover:text-[#29252A] rounded-lg"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="p-4">
        <button
          type="button"
          onClick={() => {
            onNewTrip();
            onCloseMobile();
          }}
          className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-[#641C32] px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#873B52] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#641C32] focus-visible:ring-offset-2 whitespace-nowrap"
        >
          <Plus className="h-4 w-4 shrink-0" />
          <span>New Trip</span>
        </button>
      </div>

      <nav className="px-3 space-y-1">
        <button
          type="button"
          onClick={() => {
            onNavigateDashboard();
            onCloseMobile();
          }}
          className={`w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors whitespace-nowrap ${
            activePage === 'dashboard'
              ? 'bg-[#F3E7EB] text-[#641C32]'
              : 'text-[#524A4E] hover:bg-[#FAF9F7] hover:text-[#29252A]'
          }`}
        >
          <LayoutDashboard className="h-4 w-4 shrink-0" />
          <span>Dashboard</span>
        </button>

        <button
          type="button"
          onClick={() => {
            onNavigateNotifications();
            onCloseMobile();
          }}
          className={`w-full flex items-center justify-between rounded-lg px-3 py-2.5 text-sm font-medium transition-colors whitespace-nowrap ${
            activePage === 'notifications'
              ? 'bg-[#F3E7EB] text-[#641C32]'
              : 'text-[#524A4E] hover:bg-[#FAF9F7] hover:text-[#29252A]'
          }`}
        >
          <span className="flex items-center gap-3">
            <Bell className="h-4 w-4 shrink-0" />
            <span>Notifications</span>
          </span>
          {unreadCount > 0 && (
            <span className="font-mono text-xs font-semibold text-[#641C32] tabular-nums">
              {unreadCount}
            </span>
          )}
        </button>
      </nav>

      <div className="mt-5 flex-1 overflow-y-auto px-3 pb-6">
        {activeTrips.length > 0 && (
          <div className="mb-5">
            <div className="px-3 pb-2 text-xs font-semibold text-[#873B52] tracking-wide">
              Active Trips
            </div>
            <div className="space-y-0.5">
              {activeTrips.map((trip) => {
                const isSelected = activePage === 'trip' && selectedTripId === trip.id;
                return (
                  <button
                    key={trip.id}
                    type="button"
                    onClick={() => {
                      onSelectTrip(trip.id);
                      onCloseMobile();
                    }}
                    className={`w-full text-left rounded-lg px-3 py-2 transition-colors ${
                      isSelected
                        ? 'bg-[#F3E7EB] text-[#641C32]'
                        : 'text-[#29252A] hover:bg-[#FAF9F7]'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <MapPin className="h-3.5 w-3.5 shrink-0 text-[#873B52]" />
                      <span className="truncate text-sm font-medium">{trip.name}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {completedTrips.length > 0 && (
          <div>
            <div className="px-3 pb-2 text-xs font-semibold text-[#6E656B] tracking-wide">
              Completed Trips
            </div>
            <div className="space-y-0.5">
              {completedTrips.map((trip) => {
                const isSelected = activePage === 'trip' && selectedTripId === trip.id;
                return (
                  <button
                    key={trip.id}
                    type="button"
                    onClick={() => {
                      onSelectTrip(trip.id);
                      onCloseMobile();
                    }}
                    className={`w-full text-left rounded-lg px-3 py-2 transition-colors ${
                      isSelected
                        ? 'bg-[#F3E7EB] text-[#641C32]'
                        : 'text-[#524A4E] hover:bg-[#FAF9F7]'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <MapPin className="h-3.5 w-3.5 shrink-0 text-[#B9788B]" />
                      <span className="truncate text-sm font-medium">{trip.name}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop persistent sidebar */}
      <aside className="hidden lg:block w-64 shrink-0 h-screen sticky top-0">
        {navContent}
      </aside>

      {/* Mobile top header bar (<= 15% height) */}
      <header className="lg:hidden sticky top-0 z-30 flex items-center justify-between bg-white border-b border-[#E9E2E4] px-4 py-3">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onOpenMobile}
            aria-label="Open navigation"
            className="p-2 -ml-2 text-[#29252A] hover:bg-[#FAF9F7] rounded-lg"
          >
            <Menu className="h-5 w-5" />
          </button>
          <button
            type="button"
            onClick={onNavigateDashboard}
            className="font-display text-base font-bold text-[#641C32] whitespace-nowrap"
          >
            TripLedger
          </button>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onNavigateNotifications}
            aria-label="Notifications"
            className="relative p-2 text-[#524A4E] hover:bg-[#FAF9F7] rounded-lg"
          >
            <Bell className="h-5 w-5" />
            {unreadCount > 0 && (
              <span className="absolute top-1 right-1 font-mono text-[10px] font-bold text-[#641C32]">
                {unreadCount}
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={onNewTrip}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#641C32] px-3 py-2 text-xs font-medium text-white hover:bg-[#873B52] whitespace-nowrap"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>New Trip</span>
          </button>
        </div>
      </header>

      {/* Mobile slide-over drawer */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div
            className="fixed inset-0 bg-[#29252A]/40"
            onClick={onCloseMobile}
            aria-hidden="true"
          />
          <div className="relative z-10 w-72 max-w-[85vw] h-full">{navContent}</div>
        </div>
      )}
    </>
  );
}
