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

// Map ProdPlan orders stats to Alpha stat cards
export function mapToStatCards(ordersStats?: OrdersStats, oeeValue?: number): StatCardData[] {
  return [
    {
      icon: Package,
      iconBg: 'bg-accent-muted',
      label: 'Total Orders',
      value: ordersStats?.total ?? 1200,
      change: { value: 59, label: 'vs last month' },
    },
    {
      icon: MapPin,
      iconBg: 'bg-accent-muted',
      label: 'Avg. Lead Time',
      value: ordersStats?.byPriority?.high ?? 530,
      unit: 'hrs',
      change: { value: -16, label: 'vs last month' },
    },
    {
      icon: Truck,
      iconBg: 'bg-accent-muted',
      label: 'Completed',
      value: ordersStats?.byStatus?.completed ?? 3047,
      change: { value: 59, label: 'vs last month' },
    },
    {
      icon: Scale,
      iconBg: 'bg-accent-muted',
      label: 'Avg. OEE',
      value: oeeValue ?? 248,
      unit: '%',
      change: { value: 5, label: 'vs last month' },
    },
  ];
}

// Map production data to income tracker format
export function mapToIncomeTracker(weeklyData?: any[]): IncomeTrackerData[] {
  if (!weeklyData || weeklyData.length === 0) {
    return [
      { label: 'Mon', value: 120 },
      { label: 'Tue', value: 180 },
      { label: 'Wed', value: 250 },
      { label: 'Thu', value: 329 },
      { label: 'Fri', value: 200 },
      { label: 'Sat', value: 90 },
      { label: 'Sun', value: 150 },
    ];
  }
  
  return weeklyData.map((item, index) => ({
    label: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][index] || `Day ${index + 1}`,
    value: item.value || item.production || item.count || 0,
  }));
}

// Map orders to recent activities format
export function mapToRecentActivities(orders?: any[]): ActivityData[] {
  if (!orders || orders.length === 0) {
    return [
      { id: '#1032-392pk', category: 'Electronic', arrivalTime: '7 Jul, 2024', status: 'Delivered' },
      { id: '#1032-393pk', category: 'Cosmetic', arrivalTime: '16 May, 2024', status: 'In Transit' },
      { id: '#1032-394pk', category: 'Furniture', arrivalTime: '22 Jun, 2024', status: 'Pending' },
      { id: '#1032-395pk', category: 'Food', arrivalTime: '3 Jul, 2024', status: 'Processing' },
    ];
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

// Map order tracking to timeline events
export function mapToTrackingEvents(orderPhases?: any[]): TimelineEventData[] {
  if (!orderPhases || orderPhases.length === 0) {
    return [
      {
        id: '1',
        title: 'Your package is being delivered up by courier',
        location: 'Warehouse',
        time: '09:12 AM',
        date: 'Today',
        status: 'active',
        courier: {
          name: 'Production Team',
          avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Team',
        },
      },
      {
        id: '2',
        title: 'In Transit',
        location: 'Production Line',
        time: '09:12 AM',
        date: 'Today',
        status: 'completed',
      },
    ];
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

// Map products to visits by country format
export function mapToVisitsByCountry(productStats?: any[]) {
  if (!productStats || productStats.length === 0) {
    return [
      { value: 4743, percentage: 50, label: 'K1 Products', change: 4.53 },
      { value: 9759, percentage: 100, label: 'K2 Products', change: 8.15 },
      { value: 604, percentage: 20, label: 'Custom Orders', change: -2.30 },
    ];
  }

  const maxValue = Math.max(...productStats.map(p => p.count || p.value || 0));
  
  return productStats.slice(0, 3).map((product) => ({
    value: product.count || product.value || 0,
    percentage: Math.round(((product.count || product.value || 0) / maxValue) * 100),
    label: product.name || product.type || 'Product',
    change: product.change || Math.random() * 10 - 2,
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




