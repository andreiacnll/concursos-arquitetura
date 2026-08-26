"use client";

import type { CSSProperties, ReactNode } from "react";
import { Filter, X } from "lucide-react";
import type {
  CompetitionFiltersState,
  DeadlineFilter,
} from "./competition-filters";
import {
  getCompetitionPriceRange,
  procedureOptions,
  serviceOptions,
  type CompetitionFilterItem,
} from "./competition-filters";

type Props = {
  items: CompetitionFilterItem[];
  districts: string[];
  filters: CompetitionFiltersState;
  onChange: (filters: CompetitionFiltersState) => void;
  onClear: () => void;
  hasActiveFilters: boolean;
  mobileOpen?: boolean;
  onCloseMobile?: () => void;
  contextContent?: ReactNode;
};

function formatPriceFilter(value: number) {
  return new Intl.NumberFormat("pt-PT", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

function updateList(current: string[], value: string) {
  return current.includes(value)
    ? current.filter((item) => item !== value)
    : [...current, value];
}

export default function CompetitionFiltersSidebar({
  items,
  districts,
  filters,
  onChange,
  onClear,
  hasActiveFilters,
  mobileOpen = false,
  onCloseMobile,
  contextContent,
}: Props) {
  const priceRange = getCompetitionPriceRange(items);
  const priceScaleMin = priceRange ? Math.min(0, priceRange.min) : 0;
  const selectedPriceMin = priceRange
    ? Math.max(
        priceScaleMin,
        Math.min(Number(filters.precoMin || priceScaleMin), priceRange.max),
      )
    : 0;
  const selectedPriceMax = priceRange
    ? Math.max(
        selectedPriceMin,
        Math.min(Number(filters.precoMax || priceRange.max), priceRange.max),
      )
    : 0;

  const panel = (
    <aside className="filters-panel">
      <div className="filters-title">
        <Filter size={17} />
        <span>Filtrar</span>
        {onCloseMobile && (
          <button
            type="button"
            className="filters-close-button"
            aria-label="Fechar filtros"
            onClick={onCloseMobile}
          >
            <X size={17} />
          </button>
        )}
      </div>

      {contextContent}

      <div className="filter-group">
        <label htmlFor="district">Distrito</label>
        <select
          id="district"
          value={filters.district}
          onChange={(event) =>
            onChange({ ...filters, district: event.target.value })
          }
        >
          <option>Todos os distritos</option>
          {districts.map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <p>Intervalo de preço</p>
        {priceRange ? (
          <div className="dynamic-price-filter">
            <div className="dynamic-price-values">
              <strong>{formatPriceFilter(selectedPriceMin)}</strong>
              <strong>{formatPriceFilter(selectedPriceMax)}</strong>
            </div>
            <div
              className="dynamic-price-slider"
              style={
                {
                  "--price-start": `${
                    ((selectedPriceMin - priceScaleMin) /
                      Math.max(priceRange.max - priceScaleMin, 1)) *
                    100
                  }%`,
                  "--price-end": `${
                    ((selectedPriceMax - priceScaleMin) /
                      Math.max(priceRange.max - priceScaleMin, 1)) *
                    100
                  }%`,
                } as CSSProperties
              }
            >
              <input
                type="range"
                min={priceScaleMin}
                max={priceRange.max}
                step="any"
                value={selectedPriceMin}
                aria-label="Valor mínimo"
                onChange={(event) =>
                  onChange({
                    ...filters,
                    precoMin: String(
                      Math.min(Number(event.target.value), selectedPriceMax),
                    ),
                  })
                }
              />
              <input
                type="range"
                min={priceScaleMin}
                max={priceRange.max}
                step="any"
                value={selectedPriceMax}
                aria-label="Valor máximo"
                onChange={(event) =>
                  onChange({
                    ...filters,
                    precoMax: String(
                      Math.max(Number(event.target.value), selectedPriceMin),
                    ),
                  })
                }
              />
            </div>
            <div className="dynamic-price-extremes">
              <span>{formatPriceFilter(priceScaleMin)}</span>
              <span>{formatPriceFilter(priceRange.max)}</span>
            </div>
            <small>
              {priceRange.count} concursos com valor · menor valor encontrado:{" "}
              {formatPriceFilter(priceRange.min)}
            </small>
          </div>
        ) : (
          <p className="dynamic-price-empty">
            Sem valores disponíveis nos concursos atuais.
          </p>
        )}
      </div>

      <div className="filter-group">
        <label htmlFor="entity-filter">Entidade promotora</label>
        <input
          id="entity-filter"
          className="filter-text-input"
          value={filters.entidadeQuery}
          onChange={(event) =>
            onChange({ ...filters, entidadeQuery: event.target.value })
          }
          placeholder="Pesquisar entidade"
        />
      </div>

      <div className="filter-group">
        <label htmlFor="deadline-filter">Prazo de entrega</label>
        <select
          id="deadline-filter"
          value={filters.prazoFilter}
          onChange={(event) =>
            onChange({
              ...filters,
              prazoFilter: event.target.value as DeadlineFilter,
            })
          }
        >
          <option value="todos">Todos os prazos</option>
          <option value="7">Próximos 7 dias</option>
          <option value="15">Próximos 15 dias</option>
          <option value="30">Próximos 30 dias</option>
        </select>
      </div>

      <div className="filter-group">
        <p>Tipo de procedimento</p>
        {procedureOptions.map((label) => (
          <label className="check-row" key={label}>
            <input
              type="checkbox"
              checked={filters.selectedProcedures.includes(label)}
              onChange={() =>
                onChange({
                  ...filters,
                  selectedProcedures: updateList(
                    filters.selectedProcedures,
                    label,
                  ),
                })
              }
            />
            <span>{label}</span>
          </label>
        ))}
      </div>

      <div className="filter-group">
        <p>Tipo de serviço</p>
        {serviceOptions.map((label) => (
          <label className="check-row" key={label}>
            <input
              type="checkbox"
              checked={filters.selectedServices.includes(label)}
              onChange={() =>
                onChange({
                  ...filters,
                  selectedServices: updateList(filters.selectedServices, label),
                })
              }
            />
            <span>{label}</span>
          </label>
        ))}
      </div>

      {hasActiveFilters && (
        <div className="filter-group">
          <button
            type="button"
            className="clear-filters-button"
            onClick={onClear}
          >
            Limpar filtros
          </button>
        </div>
      )}
    </aside>
  );

  if (!onCloseMobile) return panel;

  return (
    <div
      className={`filters-mobile-drawer ${mobileOpen ? "open" : ""}`}
      aria-hidden={!mobileOpen}
    >
      <button
        type="button"
        className="filters-mobile-backdrop"
        aria-label="Fechar filtros"
        onClick={onCloseMobile}
      />
      {panel}
    </div>
  );
}
