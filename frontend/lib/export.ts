/**
 * Export utility — download any table data as CSV or XLSX.
 * Reusable across all pages.
 */
import * as XLSX from "xlsx";

export interface ExportColumn {
  key: string;
  label: string;
  format?: (value: any) => string | number;
}

/**
 * Export rows to CSV and trigger browser download.
 */
export function exportCSV(
  rows: Record<string, any>[],
  columns: ExportColumn[],
  filename: string
) {
  const header = columns.map((c) => c.label).join(",");
  const lines = rows.map((row) =>
    columns
      .map((col) => {
        const val = col.format ? col.format(row[col.key]) : row[col.key];
        const str = val == null ? "" : String(val);
        // Escape commas and quotes
        return str.includes(",") || str.includes('"') || str.includes("\n")
          ? `"${str.replace(/"/g, '""')}"`
          : str;
      })
      .join(",")
  );
  const csv = [header, ...lines].join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
  _download(blob, `${filename}.csv`);
}

/**
 * Export rows to XLSX and trigger browser download.
 */
export function exportXLSX(
  rows: Record<string, any>[],
  columns: ExportColumn[],
  filename: string
) {
  const data = rows.map((row) => {
    const obj: Record<string, any> = {};
    for (const col of columns) {
      obj[col.label] = col.format ? col.format(row[col.key]) : row[col.key] ?? "";
    }
    return obj;
  });

  const ws = XLSX.utils.json_to_sheet(data);

  // Auto-width columns
  const colWidths = columns.map((col) => {
    const maxLen = Math.max(
      col.label.length,
      ...rows.map((r) => {
        const v = col.format ? col.format(r[col.key]) : r[col.key];
        return v == null ? 0 : String(v).length;
      })
    );
    return { wch: Math.min(maxLen + 2, 50) };
  });
  ws["!cols"] = colWidths;

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Data");
  XLSX.writeFile(wb, `${filename}.xlsx`);
}

function _download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
