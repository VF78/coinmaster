import type { ReactNode } from 'react';

interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
}

interface DataTableProps<T extends { id: string }> {
  columns: Column<T>[];
  rows: T[];
  mobileTitle: (row: T) => string;
  mobileSubtitle?: (row: T) => string;
  emptyText?: string;
}

export function DataTable<T extends { id: string }>({
  columns,
  rows,
  mobileTitle,
  mobileSubtitle,
  emptyText = 'No data yet'
}: DataTableProps<T>) {
  if (!rows.length) {
    return <p className="muted">{emptyText}</p>;
  }

  return (
    <>
      <div className="table-wrap desktop-only">
        <table>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key}>{column.header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                {columns.map((column) => (
                  <td key={column.key}>{column.render(row)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mobile-cards mobile-only">
        {rows.map((row) => (
          <article key={row.id} className="mobile-card">
            <header className="mobile-card__header">
              <h3>{mobileTitle(row)}</h3>
              {mobileSubtitle ? <p>{mobileSubtitle(row)}</p> : null}
            </header>
            <dl>
              {columns.map((column) => (
                <div key={column.key} className="mobile-card__row">
                  <dt>{column.header}</dt>
                  <dd>{column.render(row)}</dd>
                </div>
              ))}
            </dl>
          </article>
        ))}
      </div>
    </>
  );
}
