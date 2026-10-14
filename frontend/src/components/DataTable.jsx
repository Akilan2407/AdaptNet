import React, { useState, useMemo } from 'react';
import { IconSearch, IconChevronLeft, IconChevronRight } from './Icons';

export default function DataTable({
  columns = [],
  data = [],
  loading = false,
  error = null,
  emptyMessage = 'No records found.',
  searchable = true,
  searchPlaceholder = 'Filter records...',
  pagination = null, // { page, pageSize, total, onPageChange }
  onRowClick = null,
  selectedRowKey = null,
  rowKey = 'id',
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });

  // Filter rows based on search input if client-side search is enabled
  const filteredData = useMemo(() => {
    if (!searchTerm.trim()) return data;
    const term = searchTerm.toLowerCase();
    return data.filter((row) =>
      columns.some((col) => {
        const val = row[col.key];
        return val !== undefined && val !== null && String(val).toLowerCase().includes(term);
      })
    );
  }, [data, searchTerm, columns]);

  // Sort rows if column header clicked
  const sortedData = useMemo(() => {
    if (!sortConfig.key) return filteredData;
    return [...filteredData].sort((a, b) => {
      const aVal = a[sortConfig.key];
      const bVal = b[sortConfig.key];
      if (aVal === bVal) return 0;
      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;
      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
      return sortConfig.direction === 'asc' ? 1 : -1;
    });
  }, [filteredData, sortConfig]);

  const handleSort = (key) => {
    setSortConfig((prev) => {
      if (prev.key === key) {
        return { key, direction: prev.direction === 'asc' ? 'desc' : 'asc' };
      }
      return { key, direction: 'asc' };
    });
  };

  return (
    <div className="data-table-container">
      {searchable && (
        <div className="table-toolbar">
          <div className="search-box">
            <IconSearch size={14} color="#78716c" />
            <input
              type="text"
              placeholder={searchPlaceholder}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="search-input"
            />
          </div>
          <div className="table-count-label">
            Showing {sortedData.length} {pagination?.total ? `of ${pagination.total}` : 'records'}
          </div>
        </div>
      )}

      <div className="table-scroll-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  style={col.width ? { width: col.width } : {}}
                  className={col.sortable !== false ? 'sortable-header' : ''}
                  onClick={() => col.sortable !== false && handleSort(col.key)}
                >
                  <div className="th-content">
                    <span>{col.label}</span>
                    {sortConfig.key === col.key && (
                      <span className="sort-arrow">
                        {sortConfig.direction === 'asc' ? '▲' : '▼'}
                      </span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }).map((_, rIdx) => (
                <tr key={`skel-${rIdx}`}>
                  {columns.map((col, cIdx) => (
                    <td key={`skel-c-${cIdx}`}>
                      <div className="skeleton skeleton-row"></div>
                    </td>
                  ))}
                </tr>
              ))
            ) : sortedData.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="table-empty-cell">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              sortedData.map((row, idx) => {
                const rKey = row[rowKey] || idx;
                const isSelected = selectedRowKey && String(row[rowKey]) === String(selectedRowKey);
                return (
                  <tr
                    key={rKey}
                    onClick={() => onRowClick && onRowClick(row)}
                    className={`${onRowClick ? 'clickable-row' : ''} ${isSelected ? 'row-selected' : ''}`}
                  >
                    {columns.map((col) => (
                      <td key={col.key} className={col.className || ''}>
                        {col.render ? col.render(row[col.key], row) : (row[col.key] !== undefined && row[col.key] !== null ? String(row[col.key]) : '—')}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {pagination && (
        <div className="table-pagination">
          <span className="pagination-info">
            Page <strong>{pagination.page + 1}</strong> of{' '}
            <strong>{Math.max(1, Math.ceil((pagination.total || 1) / (pagination.pageSize || 10)))}</strong>
          </span>
          <div className="pagination-controls">
            <button
              className="btn btn-sm btn-secondary pagination-btn"
              disabled={pagination.page <= 0}
              onClick={() => pagination.onPageChange(pagination.page - 1)}
            >
              <IconChevronLeft size={13} />
              <span>Previous</span>
            </button>
            <button
              className="btn btn-sm btn-secondary pagination-btn"
              disabled={(pagination.page + 1) * pagination.pageSize >= (pagination.total || 0)}
              onClick={() => pagination.onPageChange(pagination.page + 1)}
            >
              <span>Next</span>
              <IconChevronRight size={13} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
