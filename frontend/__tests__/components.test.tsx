import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { PeriodFilter } from "../components/period-filter";
import { DataTable } from "../components/tables/data-table";

describe("PeriodFilter component", () => {
  it("renders all 4 preset buttons", () => {
    const onChange = vi.fn();
    render(<PeriodFilter selectedDays={30} onDaysChange={onChange} />);
    expect(screen.getByText("7j")).toBeDefined();
    expect(screen.getByText("30j")).toBeDefined();
    expect(screen.getByText("90j")).toBeDefined();
    expect(screen.getByText("12 mois")).toBeDefined();
  });

  it("calls onDaysChange when clicking a preset", () => {
    const onChange = vi.fn();
    render(<PeriodFilter selectedDays={30} onDaysChange={onChange} />);
    fireEvent.click(screen.getByText("7j"));
    expect(onChange).toHaveBeenCalledWith(7);
  });

  it("calls onDaysChange with 365 for '12 mois'", () => {
    const onChange = vi.fn();
    render(<PeriodFilter selectedDays={30} onDaysChange={onChange} />);
    fireEvent.click(screen.getByText("12 mois"));
    expect(onChange).toHaveBeenCalledWith(365);
  });
});

describe("DataTable component", () => {
  const columns = [
    { key: "name" as const, header: "Nom" },
    { key: "score" as const, header: "Score" },
  ];

  it("renders headers", () => {
    render(<DataTable data={[]} columns={columns} />);
    expect(screen.getByText("Nom")).toBeDefined();
    expect(screen.getByText("Score")).toBeDefined();
  });

  it("renders data rows", () => {
    const data = [
      { name: "Carrefour", score: 85 },
      { name: "Lidl", score: 72 },
    ];
    render(<DataTable data={data} columns={columns} />);
    expect(screen.getByText("Carrefour")).toBeDefined();
    expect(screen.getByText("Lidl")).toBeDefined();
    expect(screen.getByText("85")).toBeDefined();
  });

  it("shows empty message when no data", () => {
    render(<DataTable data={[]} columns={columns} />);
    expect(screen.getByText("Aucune donnee disponible")).toBeDefined();
  });

  it("calls onRowClick when row is clicked", () => {
    const onClick = vi.fn();
    const data = [{ name: "Carrefour", score: 85 }];
    render(<DataTable data={data} columns={columns} onRowClick={onClick} />);
    fireEvent.click(screen.getByText("Carrefour"));
    expect(onClick).toHaveBeenCalledWith({ name: "Carrefour", score: 85 });
  });

  it("renders with custom render function", () => {
    const customColumns = [
      {
        key: "name" as const,
        header: "Nom",
        render: (item: { name: string }) => <strong data-testid="bold">{item.name.toUpperCase()}</strong>,
      },
    ];
    const data = [{ name: "Carrefour" }];
    render(<DataTable data={data} columns={customColumns} />);
    expect(screen.getByText("CARREFOUR")).toBeDefined();
  });

  it("renders '-' for null/undefined values", () => {
    const data = [{ name: "Test", score: undefined }];
    render(<DataTable data={data} columns={columns} />);
    expect(screen.getByText("-")).toBeDefined();
  });
});
