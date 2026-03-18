import { FileText } from 'lucide-react';
import QueueStatusIndicator from './QueueStatusIndicator';

export default function Layout({ children }) {
  return (
    <div className="min-h-screen bg-gray-100">
      {/* Top header */}
      <header className="bg-gray-800 text-white px-6 py-3 flex items-center justify-between">
        <h1 className="text-lg font-bold flex items-center gap-2">
          <FileText className="w-5 h-5" />
          Doc Extract
        </h1>
        <QueueStatusIndicator />
      </header>

      {/* Main content */}
      <main className="p-6">
        {children}
      </main>
    </div>
  );
}
