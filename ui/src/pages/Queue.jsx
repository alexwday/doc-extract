import { useState, useEffect, useRef } from 'react';
import { Plus, X, Loader2, CheckCircle, XCircle, AlertCircle, Download, Trash2, Eye, RefreshCw, FileSpreadsheet, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, RotateCcw, Clock, Square, Upload, Settings, Edit2, Save, PanelRightOpen, PanelRightClose } from 'lucide-react';
import { useQueue } from '../contexts/QueueContext';
import { getDocuments, getTemplates, getResult, createExport, getExportDownloadUrl, getAnnotatedPage, uploadDocument, deleteDocument, createTemplate, updateTemplate, deleteTemplate } from '../services/api';

// Color palette matching backend
const FIELD_COLORS = [
  'rgb(220, 38, 38)',
  'rgb(37, 99, 235)',
  'rgb(22, 163, 74)',
  'rgb(217, 119, 6)',
  'rgb(147, 51, 234)',
  'rgb(236, 72, 153)',
  'rgb(6, 182, 212)',
  'rgb(249, 115, 22)',
];

const FIELD_TYPES = [
  { value: 'metric', label: 'Metric' },
  { value: 'summary', label: 'Summary' },
];

// ============================================================================
// Result Viewer Component
// ============================================================================

function ResultViewer({ result, onClose }) {
  const [currentPage, setCurrentPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [selectedField, setSelectedField] = useState(null);
  const [imageKey, setImageKey] = useState(0);

  const pageCount = result.page_count || Object.keys(result.page_ocr || {}).length || 4;
  const extractions = result.extractions || {};
  const fieldNames = Object.keys(extractions).sort();
  const fieldColors = Object.fromEntries(
    fieldNames.map((name, i) => [name, FIELD_COLORS[i % FIELD_COLORS.length]])
  );

  const metrics = Object.entries(extractions).filter(([, v]) => v.field_type !== 'summary');
  const summaries = Object.entries(extractions).filter(([, v]) => v.field_type === 'summary');
  const entityGroups = result.entity_groups || {};

  const handleZoomIn = () => setZoom((z) => Math.min(z + 0.5, 4));
  const handleZoomOut = () => setZoom((z) => Math.max(z - 0.5, 0.5));
  const handleResetZoom = () => {
    setZoom(1);
    setPosition({ x: 0, y: 0 });
    setSelectedField(null);
    setImageKey(k => k + 1);
  };

  const handleMouseDown = (e) => {
    if (zoom > 1) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
    }
  };

  const handleMouseMove = (e) => {
    if (isDragging && zoom > 1) {
      setPosition({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    }
  };

  const handleMouseUp = () => setIsDragging(false);

  const handleMetricClick = (fieldName, data) => {
    if (data.page && data.page !== currentPage) setCurrentPage(data.page);
    if (selectedField === fieldName) {
      setSelectedField(null);
      setZoom(1);
      setPosition({ x: 0, y: 0 });
    } else {
      setSelectedField(fieldName);
      setZoom(1.5);
    }
    setImageKey(k => k + 1);
  };

  useEffect(() => {
    setPosition({ x: 0, y: 0 });
    if (selectedField) {
      const fieldData = extractions[selectedField];
      if (fieldData && fieldData.page !== currentPage) {
        setSelectedField(null);
        setZoom(1);
      }
    }
    setImageKey(k => k + 1);
  }, [currentPage]);

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="flex justify-between items-center p-4 border-b">
        <div>
          <h2 className="font-bold text-lg">{result.document_name}</h2>
          {!result.verified && (
            <p className="text-sm text-amber-600 flex items-center gap-1 mt-1">
              <AlertCircle className="w-4 h-4" />
              Not verified - summaries require LLM verification
            </p>
          )}
        </div>
        <button onClick={onClose} className="px-3 py-1 border rounded hover:bg-gray-50">Close</button>
      </div>

      <div className="flex h-[600px]">
        <div className="w-1/2 border-r p-4 flex flex-col">
          <div className="flex justify-between items-center mb-2">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">Page {currentPage} of {pageCount}</span>
              <div className="flex gap-1 border-l pl-2 ml-2">
                <button onClick={() => setCurrentPage((p) => Math.max(1, p - 1))} disabled={currentPage <= 1} className="p-1 rounded hover:bg-gray-100 disabled:opacity-50">
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button onClick={() => setCurrentPage((p) => Math.min(pageCount, p + 1))} disabled={currentPage >= pageCount} className="p-1 rounded hover:bg-gray-100 disabled:opacity-50">
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={handleZoomOut} disabled={zoom <= 0.5} className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-50"><ZoomOut className="w-4 h-4" /></button>
              <span className="text-sm text-gray-500 w-12 text-center">{Math.round(zoom * 100)}%</span>
              <button onClick={handleZoomIn} disabled={zoom >= 4} className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-50"><ZoomIn className="w-4 h-4" /></button>
              <button onClick={handleResetZoom} className="p-1.5 rounded hover:bg-gray-100 ml-1"><RotateCcw className="w-4 h-4" /></button>
            </div>
          </div>
          <div
            className="flex-1 overflow-hidden border rounded-lg bg-gray-100 relative"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            style={{ cursor: zoom > 1 ? (isDragging ? 'grabbing' : 'grab') : 'default' }}
          >
            <img
              key={imageKey}
              src={getAnnotatedPage(result.id, currentPage, result.document_id, selectedField)}
              alt={`Page ${currentPage}`}
              className="w-full select-none"
              draggable={false}
              style={{
                transform: `scale(${zoom}) translate(${position.x / zoom}px, ${position.y / zoom}px)`,
                transformOrigin: 'top left',
                transition: isDragging ? 'none' : 'transform 0.2s ease-out',
              }}
            />
          </div>
        </div>

        <div className="w-1/2 p-4 overflow-auto">
          <div className="mb-6">
            <h3 className="font-medium text-gray-700 mb-3">Extracted Values ({metrics.length})</h3>
            {metrics.length === 0 ? (
              <p className="text-gray-500 text-sm">No values extracted</p>
            ) : (
              <div className="space-y-2">
                {metrics.map(([name, data]) => {
                  const isSelected = selectedField === name;
                  const color = fieldColors[name] || 'rgb(100,100,100)';
                  return (
                    <div
                      key={name}
                      onClick={() => handleMetricClick(name, data)}
                      className={`border rounded-lg p-3 cursor-pointer transition-all ${isSelected ? 'ring-2 ring-offset-1 bg-gray-50' : 'hover:bg-gray-50'}`}
                      style={{ borderColor: isSelected ? color : undefined }}
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex items-center gap-2">
                          <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                          <span className="font-medium text-sm">{data.display_name || name}</span>
                        </div>
                        <div className="flex gap-2 items-center">
                          {data.verified && <CheckCircle className="w-4 h-4 text-green-500" />}
                          <span className={`text-xs px-2 py-0.5 rounded ${data.confidence >= 0.8 ? 'bg-green-100 text-green-700' : data.confidence >= 0.5 ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'}`}>
                            {Math.round(data.confidence * 100)}%
                          </span>
                        </div>
                      </div>
                      <p className="text-gray-900 mt-1 font-mono text-sm pl-5">{data.value || 'N/A'}</p>
                      <p className="text-xs text-gray-500 mt-1 pl-5">Page {data.page}</p>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div>
            <h3 className="font-medium text-gray-700 mb-3">Summaries ({summaries.length})</h3>
            {summaries.length === 0 ? (
              <div className="text-gray-500 text-sm p-4 border border-dashed rounded-lg">
                {result.verified ? <p>No summaries were generated</p> : <p><AlertCircle className="w-4 h-4 inline mr-1" />Summaries require "Verify with LLM"</p>}
              </div>
            ) : (
              <div className="space-y-3">
                {summaries.map(([name, data]) => (
                  <div key={name} className="border rounded-lg p-3 bg-purple-50">
                    <div className="flex justify-between items-start mb-2">
                      <span className="font-medium text-sm text-purple-800">{data.display_name || name}</span>
                      <span className="text-xs text-purple-600">{data.source_pages?.length > 0 ? `Pages: ${data.source_pages.join(', ')}` : `Page ${data.page}`}</span>
                    </div>
                    <p className="text-gray-700 text-sm whitespace-pre-wrap">{data.value || 'No summary generated'}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Entity Groups */}
          {Object.keys(entityGroups).length > 0 && (
            <div className="mt-6">
              <h3 className="font-medium text-gray-700 mb-3">Entity Groups</h3>
              {Object.entries(entityGroups).map(([groupName, groupData]) => (
                <div key={groupName} className="border-2 border-green-200 rounded-lg p-3 bg-green-50 mb-4">
                  <div className="flex justify-between items-center mb-3">
                    <span className="font-medium text-green-800">{groupData.display_name || groupName}</span>
                    <span className="text-xs text-green-600 bg-green-100 px-2 py-1 rounded-full">
                      {groupData.entities?.length || 0} entities
                    </span>
                  </div>
                  {groupData.entities?.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="min-w-full text-sm">
                        <thead>
                          <tr className="border-b border-green-200">
                            <th className="px-2 py-1 text-left text-xs font-medium text-green-700">#</th>
                            <th className="px-2 py-1 text-left text-xs font-medium text-green-700">Page</th>
                            {Object.keys(groupData.entities[0]?.values || {}).map((fieldName) => (
                              <th key={fieldName} className="px-2 py-1 text-left text-xs font-medium text-green-700">
                                {fieldName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {groupData.entities.map((entity, idx) => (
                            <tr key={idx} className="border-b border-green-100 hover:bg-green-100">
                              <td className="px-2 py-1 text-gray-500">{idx + 1}</td>
                              <td className="px-2 py-1 text-gray-500">{entity.page}</td>
                              {Object.entries(entity.values || {}).map(([fieldName, value]) => (
                                <td key={fieldName} className="px-2 py-1 font-mono text-gray-900">{value}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="text-green-600 text-sm">No entities extracted</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Template Dropdown Component (Collapsible above documents)
// ============================================================================

function TemplateDropdown({ templates, onRefresh, isOpen, onToggle }) {
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [fields, setFields] = useState([]);
  const [entityGroups, setEntityGroups] = useState([]);

  const resetForm = () => {
    setName('');
    setDescription('');
    setFields([]);
    setEntityGroups([]);
    setEditingTemplate(null);
    setShowForm(false);
  };

  const startEdit = (template) => {
    setEditingTemplate(template);
    setName(template.name);
    setDescription(template.description || '');
    setFields(template.fields || []);
    setEntityGroups(template.entity_groups || []);
    setShowForm(true);
    if (!isOpen) onToggle();
  };

  const startNew = () => {
    resetForm();
    setShowForm(true);
  };

  const addField = () => {
    setFields([...fields, { name: '', display_name: '', description: '', field_type: 'metric' }]);
  };

  const updateField = (index, key, value) => {
    const newFields = [...fields];
    newFields[index] = { ...newFields[index], [key]: value };
    setFields(newFields);
  };

  const removeField = (index) => {
    setFields(fields.filter((_, i) => i !== index));
  };

  // Entity group methods
  const addEntityGroup = () => {
    setEntityGroups([...entityGroups, { name: '', display_name: '', description: '', fields: [] }]);
  };

  const updateEntityGroup = (index, key, value) => {
    const newGroups = [...entityGroups];
    newGroups[index] = { ...newGroups[index], [key]: value };
    setEntityGroups(newGroups);
  };

  const removeEntityGroup = (index) => {
    setEntityGroups(entityGroups.filter((_, i) => i !== index));
  };

  const addEntityGroupField = (groupIndex) => {
    const newGroups = [...entityGroups];
    newGroups[groupIndex].fields = [...(newGroups[groupIndex].fields || []), { name: '', display_name: '', description: '' }];
    setEntityGroups(newGroups);
  };

  const updateEntityGroupField = (groupIndex, fieldIndex, key, value) => {
    const newGroups = [...entityGroups];
    newGroups[groupIndex].fields[fieldIndex] = { ...newGroups[groupIndex].fields[fieldIndex], [key]: value };
    setEntityGroups(newGroups);
  };

  const removeEntityGroupField = (groupIndex, fieldIndex) => {
    const newGroups = [...entityGroups];
    newGroups[groupIndex].fields = newGroups[groupIndex].fields.filter((_, i) => i !== fieldIndex);
    setEntityGroups(newGroups);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      if (editingTemplate) {
        await updateTemplate(editingTemplate.id, { name, description, fields, entity_groups: entityGroups });
      } else {
        await createTemplate({ name, description, fields, entity_groups: entityGroups });
      }
      resetForm();
      onRefresh();
    } catch (err) {
      console.error('Failed to save template:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Delete this template?')) return;
    try {
      await deleteTemplate(id);
      onRefresh();
    } catch (err) {
      console.error('Failed to delete template:', err);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow mb-4">
      {/* Header - always visible */}
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex justify-between items-center hover:bg-gray-50 rounded-lg"
      >
        <div className="flex items-center gap-3">
          <Settings className="w-5 h-5 text-blue-600" />
          <span className="font-medium">Templates</span>
          <span className="text-sm text-gray-500">({templates.length})</span>
          {templates.length > 0 && !isOpen && (
            <div className="flex gap-1 ml-2">
              {templates.slice(0, 3).map((t, i) => (
                <span key={i} className="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded-full">
                  {t.name}
                </span>
              ))}
              {templates.length > 3 && (
                <span className="text-xs text-gray-400">+{templates.length - 3}</span>
              )}
            </div>
          )}
        </div>
        <ChevronRight className={`w-5 h-5 text-gray-400 transition-transform ${isOpen ? 'rotate-90' : ''}`} />
      </button>

      {/* Expandable content */}
      {isOpen && (
        <div className="border-t px-4 py-4">
          {showForm ? (
            /* Template Form */
            <div className="space-y-4">
              {/* Full-width header: Name and Description */}
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Template Name</label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g., PE Fund Statement"
                  />
                </div>
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                  <input
                    type="text"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="What type of documents will this template extract from?"
                  />
                </div>
              </div>

              {/* Two columns: Fields and Field Groups */}
              <div className="grid grid-cols-2 gap-6">
                {/* Left column - Individual Fields */}
                <div className="border-2 border-blue-200 rounded-lg p-4 bg-blue-50/50">
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <h3 className="font-semibold text-blue-800 flex items-center gap-2">
                        <span className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-xs">1</span>
                        Fields
                      </h3>
                      <p className="text-xs text-blue-600 mt-1">Single values to extract (e.g., Fund Name, Total Value, Date)</p>
                    </div>
                    <button onClick={addField} className="px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm flex items-center gap-1">
                      <Plus className="w-4 h-4" /> Add Field
                    </button>
                  </div>

                  <div className="space-y-3 max-h-72 overflow-auto">
                    {fields.map((field, index) => (
                      <div key={index} className="bg-white border border-blue-200 rounded-lg p-3 shadow-sm">
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-xs font-medium text-blue-700">Field {index + 1}</span>
                          <button onClick={() => removeField(index)} className="text-gray-400 hover:text-red-500 p-1">
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                        <div className="space-y-2">
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <label className="text-xs text-gray-500">Field ID</label>
                              <input
                                type="text"
                                value={field.name}
                                onChange={(e) => updateField(index, 'name', e.target.value)}
                                className="w-full px-2 py-1.5 text-sm border rounded focus:ring-1 focus:ring-blue-500"
                                placeholder="fund_name"
                              />
                            </div>
                            <div>
                              <label className="text-xs text-gray-500">Display Name</label>
                              <input
                                type="text"
                                value={field.display_name}
                                onChange={(e) => updateField(index, 'display_name', e.target.value)}
                                className="w-full px-2 py-1.5 text-sm border rounded focus:ring-1 focus:ring-blue-500"
                                placeholder="Fund Name"
                              />
                            </div>
                          </div>
                          <div className="grid grid-cols-3 gap-2">
                            <div>
                              <label className="text-xs text-gray-500">Type</label>
                              <select
                                value={field.field_type}
                                onChange={(e) => updateField(index, 'field_type', e.target.value)}
                                className="w-full px-2 py-1.5 text-sm border rounded focus:ring-1 focus:ring-blue-500"
                              >
                                {FIELD_TYPES.map((t) => (
                                  <option key={t.value} value={t.value}>{t.label}</option>
                                ))}
                              </select>
                            </div>
                            <div className="col-span-2">
                              <label className="text-xs text-gray-500">Description / Instructions</label>
                              <input
                                type="text"
                                value={field.description}
                                onChange={(e) => updateField(index, 'description', e.target.value)}
                                className="w-full px-2 py-1.5 text-sm border rounded focus:ring-1 focus:ring-blue-500"
                                placeholder="How to find this value..."
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                    {fields.length === 0 && (
                      <div className="text-center py-8 border-2 border-dashed border-blue-200 rounded-lg">
                        <p className="text-sm text-blue-400">No fields yet</p>
                        <p className="text-xs text-blue-300 mt-1">Click "Add Field" to define values to extract</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Right column - Field Groups */}
                <div className="border-2 border-purple-200 rounded-lg p-4 bg-purple-50/50">
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <h3 className="font-semibold text-purple-800 flex items-center gap-2">
                        <span className="w-6 h-6 bg-purple-600 text-white rounded-full flex items-center justify-center text-xs">2</span>
                        Field Groups
                      </h3>
                      <p className="text-xs text-purple-600 mt-1">Repeating rows/items (e.g., Portfolio Companies, Line Items)</p>
                    </div>
                    <button onClick={addEntityGroup} className="px-3 py-1.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm flex items-center gap-1">
                      <Plus className="w-4 h-4" /> Add Group
                    </button>
                  </div>

                  <div className="space-y-3 max-h-72 overflow-auto">
                    {entityGroups.map((group, groupIndex) => (
                      <div key={groupIndex} className="bg-white border border-purple-200 rounded-lg p-3 shadow-sm">
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-xs font-medium text-purple-700">Group {groupIndex + 1}</span>
                          <button onClick={() => removeEntityGroup(groupIndex)} className="text-gray-400 hover:text-red-500 p-1">
                            <X className="w-4 h-4" />
                          </button>
                        </div>

                        <div className="space-y-2 mb-3">
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <label className="text-xs text-gray-500">Group ID</label>
                              <input
                                type="text"
                                value={group.name}
                                onChange={(e) => updateEntityGroup(groupIndex, 'name', e.target.value)}
                                className="w-full px-2 py-1.5 text-sm border rounded focus:ring-1 focus:ring-purple-500"
                                placeholder="portfolio_companies"
                              />
                            </div>
                            <div>
                              <label className="text-xs text-gray-500">Display Name</label>
                              <input
                                type="text"
                                value={group.display_name}
                                onChange={(e) => updateEntityGroup(groupIndex, 'display_name', e.target.value)}
                                className="w-full px-2 py-1.5 text-sm border rounded focus:ring-1 focus:ring-purple-500"
                                placeholder="Portfolio Companies"
                              />
                            </div>
                          </div>
                          <div>
                            <label className="text-xs text-gray-500">Description</label>
                            <input
                              type="text"
                              value={group.description}
                              onChange={(e) => updateEntityGroup(groupIndex, 'description', e.target.value)}
                              className="w-full px-2 py-1.5 text-sm border rounded focus:ring-1 focus:ring-purple-500"
                              placeholder="What kind of items are in this group?"
                            />
                          </div>
                        </div>

                        {/* Group's Fields */}
                        <div className="border-t border-purple-200 pt-2">
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-xs font-medium text-purple-600">Fields in this group:</span>
                            <button onClick={() => addEntityGroupField(groupIndex)} className="text-purple-600 hover:text-purple-800 text-xs flex items-center gap-1 px-2 py-0.5 bg-purple-100 rounded">
                              <Plus className="w-3 h-3" /> Add
                            </button>
                          </div>
                          <div className="space-y-2">
                            {(group.fields || []).map((field, fieldIndex) => (
                              <div key={fieldIndex} className="bg-purple-50 border border-purple-100 rounded p-2">
                                <div className="flex justify-between items-center mb-1">
                                  <span className="text-xs text-purple-500">Field {fieldIndex + 1}</span>
                                  <button onClick={() => removeEntityGroupField(groupIndex, fieldIndex)} className="text-gray-400 hover:text-red-500">
                                    <X className="w-3 h-3" />
                                  </button>
                                </div>
                                <div className="grid grid-cols-2 gap-1.5">
                                  <input
                                    type="text"
                                    value={field.name}
                                    onChange={(e) => updateEntityGroupField(groupIndex, fieldIndex, 'name', e.target.value)}
                                    className="px-2 py-1 text-xs border rounded"
                                    placeholder="company_name"
                                  />
                                  <input
                                    type="text"
                                    value={field.display_name}
                                    onChange={(e) => updateEntityGroupField(groupIndex, fieldIndex, 'display_name', e.target.value)}
                                    className="px-2 py-1 text-xs border rounded"
                                    placeholder="Company Name"
                                  />
                                  <input
                                    type="text"
                                    value={field.description || ''}
                                    onChange={(e) => updateEntityGroupField(groupIndex, fieldIndex, 'description', e.target.value)}
                                    className="col-span-2 px-2 py-1 text-xs border rounded"
                                    placeholder="Description / instructions for this field"
                                  />
                                </div>
                              </div>
                            ))}
                            {(!group.fields || group.fields.length === 0) && (
                              <p className="text-xs text-purple-400 text-center py-2 border border-dashed border-purple-200 rounded">
                                Add fields that appear in each row/item
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                    {entityGroups.length === 0 && (
                      <div className="text-center py-8 border-2 border-dashed border-purple-200 rounded-lg">
                        <p className="text-sm text-purple-400">No field groups yet</p>
                        <p className="text-xs text-purple-300 mt-1">Use for tables or repeating data with multiple rows</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Form buttons - full width at bottom */}
              <div className="flex justify-end gap-3 pt-2 border-t">
                <button
                  onClick={resetForm}
                  className="px-6 py-2 border rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={!name || (fields.length === 0 && entityGroups.length === 0) || saving}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  Save Template
                </button>
              </div>
            </div>
          ) : (
            /* Template List - horizontal layout */
            <div className="flex flex-wrap gap-3 items-start">
              <button
                onClick={startNew}
                className="px-4 py-2 bg-blue-50 border-2 border-blue-300 rounded-lg text-blue-700 hover:bg-blue-100 hover:border-blue-500 flex items-center gap-2 font-medium transition-colors"
              >
                <Plus className="w-5 h-5" />
                New Template
              </button>

              {templates.map((template) => (
                <div key={template.id} className="border rounded-lg p-3 hover:shadow-sm bg-white min-w-[200px] max-w-[280px]">
                  <div className="flex justify-between items-start">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium truncate text-sm">{template.name}</h3>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {template.fields?.length || 0} fields
                        {(template.entity_groups?.length || 0) > 0 && (
                          <span className="text-purple-600 ml-1">• {template.entity_groups.length} groups</span>
                        )}
                      </p>
                    </div>
                    <div className="flex gap-1 ml-2">
                      <button onClick={() => startEdit(template)} className="p-1 text-gray-500 hover:text-blue-600" title="Edit">
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => handleDelete(template.id)} className="p-1 text-gray-500 hover:text-red-600" title="Delete">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}

              {templates.length === 0 && (
                <p className="text-sm text-gray-500 py-2">
                  No templates yet. Create one to get started.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Document List Component
// ============================================================================

function DocumentList({ documents, templates, queueItems, onAdd, onUpload, onDeleteDocument }) {
  const [selections, setSelections] = useState({});
  const [adding, setAdding] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  const inQueueDocIds = new Set(
    queueItems
      .filter(item => item.status === 'pending' || item.status === 'processing')
      .map(item => item.document_id)
  );

  const notInQueueDocs = documents.filter(d => !inQueueDocIds.has(d.id));
  const inQueueDocs = documents.filter(d => inQueueDocIds.has(d.id));

  const toggleDoc = (docId) => {
    setSelections(prev => {
      if (prev[docId]) {
        const { [docId]: removed, ...rest } = prev;
        return rest;
      } else {
        return { ...prev, [docId]: { template_id: templates[0]?.id || '', verify: true } };
      }
    });
  };

  const updateSelection = (docId, field, value) => {
    setSelections(prev => ({ ...prev, [docId]: { ...prev[docId], [field]: value } }));
  };

  const selectedDocIds = Object.keys(selections);
  const selectedDocs = documents.filter(d => selections[d.id]);
  const totalPages = selectedDocs.reduce((sum, d) => sum + d.page_count, 0);
  const allValid = selectedDocIds.every(id => selections[id].template_id);

  const handleAdd = async () => {
    if (selectedDocIds.length === 0 || !allValid) return;
    setAdding(true);
    try {
      await onAdd(selectedDocIds.map(docId => ({
        document_id: docId,
        template_id: selections[docId].template_id,
        verify: selections[docId].verify,
      })));
      setSelections({});
    } finally {
      setAdding(false);
    }
  };

  const handleUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    setUploading(true);
    try {
      for (const file of files) {
        await onUpload(file);
      }
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDeleteDoc = async (e, docId) => {
    e.stopPropagation();
    if (!confirm('Delete this document?')) return;
    if (selections[docId]) {
      const { [docId]: removed, ...rest } = selections;
      setSelections(rest);
    }
    await onDeleteDocument(docId);
  };

  const renderDocRow = (doc, isInQueue) => {
    const isSelected = !!selections[doc.id];
    const selection = selections[doc.id] || { template_id: templates[0]?.id || '', verify: true };

    return (
      <tr key={doc.id} className={`${isSelected ? 'bg-blue-50' : 'hover:bg-gray-50'} ${isInQueue ? 'opacity-60' : ''}`}>
        <td className="px-4 py-2">
          <input type="checkbox" checked={isSelected} onChange={() => toggleDoc(doc.id)} className="rounded" />
        </td>
        <td className="px-4 py-2">
          <span className="font-medium text-sm">{doc.filename}</span>
          <span className="text-gray-500 text-xs ml-2">({doc.page_count}p)</span>
          {isInQueue && <span className="text-xs text-amber-600 ml-2">(in queue)</span>}
        </td>
        <td className="px-4 py-2">
          {isSelected ? (
            <select
              value={selection.template_id}
              onChange={(e) => updateSelection(doc.id, 'template_id', e.target.value)}
              className="w-full px-2 py-1 text-sm border rounded focus:ring-2 focus:ring-blue-500"
              onClick={(e) => e.stopPropagation()}
            >
              <option value="">Select...</option>
              {templates.map(t => (<option key={t.id} value={t.id}>{t.name}</option>))}
            </select>
          ) : <span className="text-gray-400 text-sm">-</span>}
        </td>
        <td className="px-4 py-2 text-center">
          {isSelected ? (
            <input
              type="checkbox"
              checked={selection.verify}
              onChange={(e) => updateSelection(doc.id, 'verify', e.target.checked)}
              className="rounded"
              onClick={(e) => e.stopPropagation()}
            />
          ) : <span className="text-gray-300">-</span>}
        </td>
        <td className="px-4 py-2 text-right">
          {!isInQueue && (
            <button onClick={(e) => handleDeleteDoc(e, doc.id)} className="p-1 text-gray-400 hover:text-red-600" title="Delete">
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </td>
      </tr>
    );
  };

  return (
    <div className="bg-white rounded-lg shadow p-4 mb-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="font-medium">Documents</h2>
        <div className="flex items-center gap-3">
          <input ref={fileInputRef} type="file" accept=".pdf" multiple onChange={handleUpload} className="hidden" id="file-upload" />
          <label htmlFor="file-upload" className={`inline-flex items-center gap-2 px-3 py-1.5 text-sm border border-gray-300 rounded-lg cursor-pointer hover:bg-gray-50 ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}>
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            Upload PDF
          </label>
          {selectedDocIds.length > 0 && (
            <span className="text-sm text-gray-500">{selectedDocIds.length} selected, {totalPages} pages</span>
          )}
          <button
            onClick={handleAdd}
            disabled={selectedDocIds.length === 0 || !allValid || adding || templates.length === 0}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {adding ? <Loader2 className="w-5 h-5 animate-spin" /> : <Plus className="w-5 h-5" />}
            Add to Queue
          </button>
        </div>
      </div>

      {templates.length === 0 && documents.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 text-amber-700 px-3 py-2 rounded-lg mb-4 text-sm">
          Create a template first (use the Templates panel on the right).
        </div>
      )}

      {documents.length === 0 ? (
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
          <Upload className="w-10 h-10 mx-auto mb-3 text-gray-400" />
          <p className="text-gray-500">No documents yet</p>
          <p className="text-sm text-gray-400 mt-1">Upload PDFs to get started</p>
        </div>
      ) : (
        <div className="border rounded-lg overflow-hidden max-h-64 overflow-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50 sticky top-0">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase w-10"></th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Document</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase w-48">Template</th>
                <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase w-20">Verify</th>
                <th className="px-4 py-2 w-10"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {notInQueueDocs.map(doc => renderDocRow(doc, false))}
              {notInQueueDocs.length > 0 && inQueueDocs.length > 0 && (
                <tr><td colSpan={5} className="px-4 py-2 bg-gray-100"><span className="text-xs font-medium text-gray-500 uppercase">Already in Queue</span></td></tr>
              )}
              {inQueueDocs.map(doc => renderDocRow(doc, true))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Queue List Component
// ============================================================================

function QueueList({ queueStatus, onViewResult, onStopCurrent, onRemoveItem, onClearCompleted }) {
  const [exporting, setExporting] = useState(false);
  const [lastExport, setLastExport] = useState(null);

  const { items } = queueStatus;
  const completedResultIds = items.filter(i => i.result_id).map(i => i.result_id);
  const hasCompleted = items.some(i => i.status === 'completed' || i.status === 'failed');

  const handleExport = async (resultIds) => {
    setExporting(true);
    try {
      const response = await createExport(resultIds);
      setLastExport(response.data);
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setExporting(false);
    }
  };

  const handleDownload = () => {
    if (lastExport) window.open(getExportDownloadUrl(lastExport.id), '_blank');
  };

  if (items.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
        <Clock className="w-12 h-12 mx-auto mb-3 opacity-30" />
        <p>Queue is empty</p>
        <p className="text-sm mt-1">Select documents above and add to queue</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="p-4 border-b flex justify-between items-center">
        <h2 className="font-medium">Queue ({items.length})</h2>
        <div className="flex gap-2">
          {completedResultIds.length > 0 && (
            <button onClick={() => handleExport(completedResultIds)} disabled={exporting} className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 flex items-center gap-1">
              {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
              Export All
            </button>
          )}
          {hasCompleted && (
            <button onClick={onClearCompleted} className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 flex items-center gap-1">
              <Trash2 className="w-4 h-4" />
              Clear Done
            </button>
          )}
        </div>
      </div>

      {lastExport && (
        <div className="px-4 py-3 bg-green-50 border-b flex items-center justify-between">
          <div className="flex items-center gap-2 text-green-700">
            <CheckCircle className="w-5 h-5" />
            <span>Export: <strong>{lastExport.filename}</strong></span>
          </div>
          <button onClick={handleDownload} className="px-3 py-1.5 bg-green-600 text-white rounded hover:bg-green-700 flex items-center gap-1 text-sm">
            <Download className="w-4 h-4" /> Download
          </button>
        </div>
      )}

      <div className="max-h-80 overflow-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50 sticky top-0">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase w-12">#</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Document</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Template</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase w-48">Status</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase w-24">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {items.map((item, index) => {
              const isProcessing = item.status === 'processing';
              const isCompleted = item.status === 'completed';
              const isFailed = item.status === 'failed';
              const isPending = item.status === 'pending';
              const progress = item.page_count > 0 ? Math.round((item.pages_processed / item.page_count) * 100) : 0;

              return (
                <tr key={item.id} className={isProcessing ? 'bg-blue-50' : ''}>
                  <td className="px-4 py-3 text-gray-400 text-sm">{index + 1}</td>
                  <td className="px-4 py-3">
                    <span className="font-medium">{item.document_name}</span>
                    <span className="text-gray-500 text-xs ml-2">({item.page_count}p)</span>
                    {item.verify && <span className="text-xs text-blue-600 ml-2">+LLM</span>}
                  </td>
                  <td className="px-4 py-3 text-gray-500">{item.template_name}</td>
                  <td className="px-4 py-3">
                    {isPending && <span className="text-gray-500 flex items-center gap-1 text-sm"><Clock className="w-4 h-4" />Queued</span>}
                    {isProcessing && (
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 text-blue-600 text-sm">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span>Page {item.pages_processed}/{item.page_count}</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-1.5">
                          <div className="bg-blue-600 h-1.5 rounded-full transition-all" style={{ width: `${progress}%` }} />
                        </div>
                      </div>
                    )}
                    {isCompleted && (
                      <span className="text-green-600 flex items-center gap-1 text-sm">
                        <CheckCircle className="w-4 h-4" />Done
                        {item.processing_time_seconds && <span className="text-gray-400 ml-1">({item.processing_time_seconds.toFixed(1)}s)</span>}
                      </span>
                    )}
                    {isFailed && (
                      <span className="text-red-600 flex items-center gap-1 text-sm" title={item.error}>
                        <XCircle className="w-4 h-4" />{item.error === 'Stopped by user' ? 'Stopped' : 'Failed'}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      {isProcessing && <button onClick={onStopCurrent} className="p-1 text-red-600 hover:text-red-800" title="Stop"><Square className="w-5 h-5" /></button>}
                      {isCompleted && item.result_id && <button onClick={() => onViewResult(item.result_id)} className="p-1 text-blue-600 hover:text-blue-800" title="View"><Eye className="w-5 h-5" /></button>}
                      {!isProcessing && <button onClick={() => onRemoveItem(item.id)} className="p-1 text-gray-400 hover:text-red-600" title="Remove"><Trash2 className="w-5 h-5" /></button>}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function Queue() {
  const { queueStatus, loading, error, addToQueue, stopCurrent, clearCompletedItems, removeItem, refreshStatus } = useQueue();
  const [documents, setDocuments] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [dataLoading, setDataLoading] = useState(true);
  const [viewingResult, setViewingResult] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setDataLoading(true);
      const [docsRes, templatesRes] = await Promise.all([getDocuments(), getTemplates()]);
      setDocuments(docsRes.data.documents || []);
      setTemplates(templatesRes.data.templates || []);
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setDataLoading(false);
    }
  };

  const handleUpload = async (file) => {
    try {
      await uploadDocument(file);
      await loadData();
    } catch (err) {
      console.error('Failed to upload:', err);
    }
  };

  const handleDeleteDocument = async (docId) => {
    try {
      await deleteDocument(docId);
      await loadData();
    } catch (err) {
      console.error('Failed to delete:', err);
    }
  };

  const handleViewResult = async (resultId) => {
    try {
      const response = await getResult(resultId);
      setViewingResult(response.data);
    } catch (err) {
      console.error('Failed to load result:', err);
    }
  };

  if (viewingResult) {
    return <ResultViewer result={viewingResult} onClose={() => setViewingResult(null)} />;
  }

  return (
    <div className="h-[calc(100vh-60px)] overflow-auto p-4">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">{error}</div>
      )}

      {dataLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
        </div>
      ) : (
        <>
          {/* Templates dropdown at top */}
          <TemplateDropdown
            templates={templates}
            onRefresh={loadData}
            isOpen={sidebarOpen}
            onToggle={() => setSidebarOpen(!sidebarOpen)}
          />

          <DocumentList
            documents={documents}
            templates={templates}
            queueItems={queueStatus.items}
            onAdd={addToQueue}
            onUpload={handleUpload}
            onDeleteDocument={handleDeleteDocument}
          />

          <QueueList
            queueStatus={queueStatus}
            onViewResult={handleViewResult}
            onStopCurrent={stopCurrent}
            onRemoveItem={removeItem}
            onClearCompleted={clearCompletedItems}
          />
        </>
      )}
    </div>
  );
}
