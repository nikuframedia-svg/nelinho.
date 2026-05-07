import { Package, MapPin, Truck, Scale } from 'lucide-react';
import type { OrdersStats } from './api';
import type { LucideIcon } from 'lucide-react';

// Types for Alpha components
export interface StatCardData {
  icon: LucideIcon;
  iconBg: string;
  label: string;
  value: string | number;
  unit?: string;
  change: {
    value: number;
    label: string;
  };
}

export interface IncomeTrackerData {
  label: string;
  value: number;
}

export interface ActivityData {
  id: string;
  category: string;
  arrivalTime: string;
  status: 'Delivered' | 'In Transit' | 'Pending' | 'Processing';
}

export interface TimelineEventData {
  id: string;
  title: string;
  location: string;
  time: string;
  date: string;
  status: 'active' | 'completed' | 'pending';
  courier?: {
    name: string;
    avatar?: string;
  };
}

// Map ProdPlan orders stats to Alpha stat cards.
//
// Sprint Q.12 — fallbacks zero em vez de números inventados. Antes
// `?? 1200`, `value: 59` mostravam dados fabricados quando a API falhava
// (CEO ficava com a impressão de fábrica activa).
export function mapToStatCards(ordersStats?: OrdersStats, oeeValue?: number): StatCardData[] {
  return [
    {
      icon: Package,
      iconBg: 'bg-accent-muted',
      label: 'Total Orders',
      value: ordersStats?.total ?? 0,
      change: { value: 0, label: 'sem dados' },
    },
    {
      icon: MapPin,
      iconBg: 'bg-accent-muted',
      label: 'Avg. Lead Time',
      value: ordersStats?.byPriority?.high ?? 0,
      unit: 'hrs',
      change: { value: 0, label: 'sem dados' },
    },
    {
      icon: Truck,
      iconBg: 'bg-accent-muted',
      label: 'Completed',
      value: ordersStats?.byStatus?.completed ?? 0,
      change: { value: 0, label: 'sem dados' },
    },
    {
      icon: Scale,
      iconBg: 'bg-accent-muted',
      label: 'Avg. OEE',
      value: oeeValue ?? 0,
      unit: '%',
      change: { value: 0, label: 'sem dados' },
    },
  ];
}

// Map production data to income tracker format.
// Sprint Q.12 — sem dados, devolve array vazio (caller decide o que mostrar)
// em vez de inventar uma semana fictícia.
export function mapToIncomeTracker(weeklyData?: any[]): IncomeTrackerData[] {
  if (!weeklyData || weeklyData.length === 0) {
    return [];
  }

  return weeklyData.map((item, index) => ({
    label: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][index] || `Day ${index + 1}`,
    value: item.value || item.production || item.count || 0,
  }));
}

// Map orders to recent activities format.
// Sprint Q.12 — sem dados, devolve array vazio em vez de IDs inventados.
export function mapToRecentActivities(orders?: any[]): ActivityData[] {
  if (!orders || orders.length === 0) {
    return [];
  }

  const statusMap: Record<string, 'Delivered' | 'In Transit' | 'Pending' | 'Processing'> = {
    completed: 'Delivered',
    in_progress: 'In Transit',
    pending: 'Pending',
    scheduled: 'Processing',
  };

  return orders.slice(0, 10).map((order) => ({
    id: `#${order.id || order.orderId}`,
    category: order.productType || order.product?.type || 'General',
    arrivalTime: formatDate(order.deliveryDate || order.dueDate),
    status: statusMap[order.status?.toLowerCase()] || 'Pending',
  }));
}

// Map order tracking to timeline events.
// Sprint Q.12 — sem dados, devolve array vazio em vez de eventos fictícios.
export function mapToTrackingEvents(orderPhases?: any[]): TimelineEventData[] {
  if (!orderPhases || orderPhases.length === 0) {
    return [];
  }

  return orderPhases.map((phase, index) => ({
    id: String(index + 1),
    title: phase.name || phase.description || `Phase ${index + 1}`,
    location: phase.location || phase.machine || 'Production',
    time: formatTime(phase.startTime || phase.time),
    date: formatDateShort(phase.date || phase.startDate),
    status: index === 0 ? 'active' : 'completed',
    courier: index === 0 ? {
      name: phase.operator || 'Team Lead',
      avatar: `https://api.dicebear.com/7.x/avataaars/svg?seed=${phase.operator || 'default'}`,
    } : undefined,
  }));
}

// Map products to visits by country format.
// Sprint Q.12 — sem dados, devolve array vazio. Antes inventava 3 produtos
// hardcoded ("K1 Products", "K2 Products") com `Math.random()` em `change`.
export function mapToVisitsByCountry(productStats?: any[]) {
  if (!productStats || productStats.length === 0) {
    return [];
  }

  const maxValue = Math.max(...productStats.map(p => p.count || p.value || 0));

  return productStats.slice(0, 3).map((product) => ({
    value: product.count || product.value || 0,
    percentage: maxValue > 0
      ? Math.round(((product.count || product.value || 0) / maxValue) * 100)
      : 0,
    label: product.name || product.type || 'Product',
    change: product.change ?? 0,
  }));
}

// Helper functions
function formatDate(dateString?: string): string {
  if (!dateString) return 'N/A';
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' });
}

function formatDateShort(dateString?: string): string {
  if (!dateString) return 'Today';
  const date = new Date(dateString);
  const today = new Date();
  if (date.toDateString() === today.toDateString()) return 'Today';
  return date.toLocaleDateString('en-US', { day: 'numeric', month: 'short' });
}

function formatTime(timeString?: string): string {
  if (!timeString) return '09:00 AM';
  const date = new Date(timeString);
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
}




