import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Templates
export const getTemplates = () => api.get('/templates');
export const getTemplate = (id) => api.get(`/templates/${id}`);
export const createTemplate = (data) => api.post('/templates', data);
export const updateTemplate = (id, data) => api.put(`/templates/${id}`, data);
export const deleteTemplate = (id) => api.delete(`/templates/${id}`);

// Documents
export const getDocuments = () => api.get('/documents');
export const getDocument = (id) => api.get(`/documents/${id}`);
export const uploadDocument = (file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const deleteDocument = (id) => api.delete(`/documents/${id}`);
export const getPageImage = (docId, page) => `/api/documents/${docId}/pages/${page}`;

// Extraction
export const runExtraction = (documentId, templateId, verify = true) =>
  api.post('/extract', { document_id: documentId, template_id: templateId, verify });
export const getResults = () => api.get('/results');
export const getResult = (id) => api.get(`/results/${id}`);
export const deleteResult = (id) => api.delete(`/results/${id}`);
export const getAnnotatedPage = (resultId, page, documentId, highlightField = null) => {
  let url = `/api/documents/${documentId}/pages/${page}/annotated?result_id=${resultId}`;
  if (highlightField) {
    url += `&highlight=${encodeURIComponent(highlightField)}`;
  }
  return url;
};

// Batch
export const createBatchJob = (templateId, documentIds, verify = true) =>
  api.post('/batch', { template_id: templateId, document_ids: documentIds, verify });
export const getBatchJob = (id) => api.get(`/batch/${id}`);
export const getBatchJobs = () => api.get('/batch');
export const startBatchJob = (id) => api.post(`/batch/${id}/start`);
export const cancelBatchJob = (id) => api.post(`/batch/${id}/cancel`);

// Export
export const createExport = (resultIds, filename = null) =>
  api.post('/export', { result_ids: resultIds, filename });
export const getExportDownloadUrl = (id) => `/api/export/${id}`;

// Queue
export const addToQueue = (items) => api.post('/queue', { items });
export const getQueueStatus = () => api.get('/queue');
export const removeQueueItem = (itemId) => api.delete(`/queue/${itemId}`);
export const stopCurrentItem = () => api.post('/queue/stop');
export const cancelQueue = () => api.post('/queue/cancel');
export const clearCompleted = () => api.delete('/queue/completed');

export default api;
