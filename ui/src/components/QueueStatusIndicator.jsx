import { Loader2 } from 'lucide-react';
import { useQueue } from '../contexts/QueueContext';

export default function QueueStatusIndicator() {
  const { queueStatus } = useQueue();
  const { is_processing, total_pages, processed_pages, items } = queueStatus;

  const pendingCount = items.filter(i => i.status === 'pending' || i.status === 'processing').length;

  if (!is_processing && pendingCount === 0) {
    return null;
  }

  const percentage = total_pages > 0 ? Math.round((processed_pages / total_pages) * 100) : 0;

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2 text-sm">
        <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
        <span className="text-gray-300">Processing</span>
      </div>
      <div className="w-24 bg-gray-600 rounded-full h-1.5">
        <div
          className="bg-blue-500 h-1.5 rounded-full transition-all duration-500"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-xs text-gray-400">{percentage}%</span>
    </div>
  );
}
