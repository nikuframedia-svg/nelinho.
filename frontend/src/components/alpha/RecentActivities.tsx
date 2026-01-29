import { MoreVertical, SlidersHorizontal } from 'lucide-react';
import { cn } from '../../lib/utils';

interface Activity {
  id: string;
  category: string;
  arrivalTime: string;
  status: 'Delivered' | 'In Transit' | 'Pending' | 'Processing';
}

interface RecentActivitiesProps {
  activities?: Activity[];
  currentPage?: number;
  totalItems?: number;
  itemsPerPage?: number;
}

const defaultActivities: Activity[] = [
  { id: '#1032-392pk', category: 'Electronic', arrivalTime: '7 Jul, 2024', status: 'Delivered' },
  { id: '#1032-393pk', category: 'Cosmetic', arrivalTime: '16 May, 2024', status: 'In Transit' },
  { id: '#1032-394pk', category: 'Furniture', arrivalTime: '22 Jun, 2024', status: 'Pending' },
  { id: '#1032-395pk', category: 'Food', arrivalTime: '3 Jul, 2024', status: 'Processing' },
];

const statusStyles = {
  'Delivered': 'text-success',
  'In Transit': 'text-info',
  'Pending': 'text-warning',
  'Processing': 'text-accent',
};

export function RecentActivities({
  activities = defaultActivities,
  currentPage = 1,
  totalItems = 23,
  itemsPerPage = 10,
}: RecentActivitiesProps) {
  const startItem = (currentPage - 1) * itemsPerPage + 1;
  const endItem = Math.min(currentPage * itemsPerPage, totalItems);

  return (
    <div className="alpha-card">
      {/* Header */}
      <div className="flex items-center justify-between mb-1">
        <div>
          <h3 className="text-base font-semibold text-text-white">Recent Activities</h3>
          <p className="text-sm text-text-muted">Track your activity here</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-text-muted">
            {startItem}-{endItem} of {totalItems}
          </span>
          <button className="flex items-center gap-2 px-3 py-1.5 bg-bg-elevated border border-border-subtle rounded-lg text-sm text-text-secondary hover:bg-bg-card-hover transition-colors">
            <SlidersHorizontal size={14} />
            Customize
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="mt-4">
        <table className="alpha-table">
          <thead>
            <tr>
              <th>Order ID</th>
              <th>Category</th>
              <th>Arrival Time</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {activities.map((activity, index) => (
              <tr key={index}>
                <td className="font-medium text-text-white">{activity.id}</td>
                <td>{activity.category}</td>
                <td>{activity.arrivalTime}</td>
                <td>
                  <span className={cn('alpha-table-status', statusStyles[activity.status])}>
                    {activity.status}
                  </span>
                </td>
                <td>
                  <button className="alpha-menu-btn">
                    <MoreVertical size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}







