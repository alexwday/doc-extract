import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { getQueueStatus, addToQueue as apiAddToQueue, stopCurrentItem as apiStopCurrent, cancelQueue as apiCancelQueue, clearCompleted as apiClearCompleted, removeQueueItem as apiRemoveQueueItem } from '../services/api';

const QueueContext = createContext(null);

export function QueueProvider({ children }) {
  const [queueStatus, setQueueStatus] = useState({
    items: [],
    is_processing: false,
    total_pages: 0,
    processed_pages: 0,
    current_item_id: null,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const pollingRef = useRef(null);

  const refreshStatus = useCallback(async () => {
    try {
      const response = await getQueueStatus();
      setQueueStatus(response.data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const addToQueue = useCallback(async (items) => {
    const response = await apiAddToQueue(items);
    setQueueStatus(response.data);
    return response.data;
  }, []);

  const stopCurrent = useCallback(async () => {
    await apiStopCurrent();
    await refreshStatus();
  }, [refreshStatus]);

  const cancelQueue = useCallback(async () => {
    await apiCancelQueue();
    await refreshStatus();
  }, [refreshStatus]);

  const clearCompletedItems = useCallback(async () => {
    await apiClearCompleted();
    await refreshStatus();
  }, [refreshStatus]);

  const removeItem = useCallback(async (itemId) => {
    await apiRemoveQueueItem(itemId);
    await refreshStatus();
  }, [refreshStatus]);

  // Initial fetch
  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  // Polling when processing
  useEffect(() => {
    if (queueStatus.is_processing) {
      pollingRef.current = setInterval(refreshStatus, 3000);
    } else {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    }

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [queueStatus.is_processing, refreshStatus]);

  const value = {
    queueStatus,
    loading,
    error,
    addToQueue,
    stopCurrent,
    cancelQueue,
    clearCompletedItems,
    removeItem,
    refreshStatus,
  };

  return (
    <QueueContext.Provider value={value}>
      {children}
    </QueueContext.Provider>
  );
}

export function useQueue() {
  const context = useContext(QueueContext);
  if (!context) {
    throw new Error('useQueue must be used within a QueueProvider');
  }
  return context;
}
