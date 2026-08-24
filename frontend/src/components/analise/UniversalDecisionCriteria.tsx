"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Target,
} from "lucide-react";
import {
  buildDecisionCriteria,
  cleanUniversal,
} from "@/lib/analysis-universal";

type AnyRecord = Record<string, any>;

type Props = {
  ficha: AnyRecord;
  procedureAnalysis: AnyRecord;
  criteriaSummary?: string;
  fallbackItems?: string[];
};

function prettyWeight(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "";

  if (Math.abs(value - Math.round(value)) < 0.0001) {
    return String(Math.round(value));
  }

  return value.toFixed(1).replace(".", ",");
}

function isDocumentedProvenance(label: string): boolean {
  return cleanUniversal(label)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .includes("confirmado nas pecas");
}

export default function UniversalDecisionCriteria({
  ficha,
  procedureAnalysis,
  criteriaSummary = "",
  fallbackItems = [],
}: Props) {
  const criteria = buildDecisionCriteria(
    ficha,
    procedureAnalysis,
    criteriaSummary,
  );

  if (criteria.length) {
    return (
      <div className="dc-award-fit-list">
        {criteria.slice(0, 8).map((item) => {
          const Icon =
            item.status === "confirmed"
              ? CheckCircle2
              : item.status === "missing"
                ? AlertTriangle
                : Target;

          const mainWeight = prettyWeight(item.weight);
          const globalWeight = prettyWeight(item.globalWeight);

          const mainNumber = Number(
            String(mainWeight).replace(",", "."),
          );
          const globalNumber = Number(
            String(globalWeight).replace(",", "."),
          );

          const showGlobal =
            Boolean(mainWeight) &&
            Boolean(globalWeight) &&
            item.weightContext === "do fator" &&
            Number.isFinite(mainNumber) &&
            Number.isFinite(globalNumber) &&
            Math.abs(mainNumber - globalNumber) > 0.0001;

          const visibleStatus = isDocumentedProvenance(item.statusLabel)
            ? "✓"
            : item.statusLabel;

          return (
            <div className="dc-award-fit-row" key={item.key}>
              <Icon size={15} />
              <div>
                <strong>{item.label}</strong>
                <span title={item.statusLabel}>
                  {mainWeight
                    ? `${mainWeight}% ${item.weightContext}`
                    : "Peso por confirmar"}
                  {showGlobal
                    ? ` · ${globalWeight}% global`
                    : ""}
                  {" · "}
                  {visibleStatus}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  const fallback = fallbackItems
    .map(cleanUniversal)
    .filter(Boolean)
    .slice(0, 5);

  if (!fallback.length) {
    return <p className="dc-empty">Critério por confirmar nas peças.</p>;
  }

  return (
    <div className="dc-award-fit-list">
      {fallback.map((item) => (
        <div className="dc-award-fit-row" key={item}>
          <Target size={15} />
          <div>
            <strong>{item}</strong>
            <span>Relevância geral da empresa</span>
          </div>
        </div>
      ))}
    </div>
  );
}
