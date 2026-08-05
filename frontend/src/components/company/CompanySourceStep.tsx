"use client";

import type { ReactNode } from "react";
import {
  Building2,
  FileText,
  FileUp,
  Globe,
  Link2,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  UserRoundPen,
} from "lucide-react";
import type {
  CompanyCreationChoice,
  CompanyProfilePath,
  CompanySearchResult,
  CompanySourceStatus,
} from "./company-types";
import type { CompanyOnboardingFileMeta } from "./company-onboarding-draft";

type Props = {
  companyName: string;
  website: string;
  companyChoice: CompanyCreationChoice;
  profilePath: CompanyProfilePath;
  portfolioFiles: File[];
  institutionalFiles: File[];
  portfolioFileMeta: CompanyOnboardingFileMeta[];
  institutionalFileMeta: CompanyOnboardingFileMeta[];
  searchResults: CompanySearchResult[];
  searchLoading: boolean;
  searchError: string | null;
  selectedExistingCompanyId: number | null;
  sourceStatuses: CompanySourceStatus[];
  hasExistingCompany: boolean;
  onCompanyNameChange: (value: string) => void;
  onWebsiteChange: (value: string) => void;
  onCompanyChoiceChange: (value: CompanyCreationChoice) => void;
  onProfilePathChange: (value: CompanyProfilePath) => void;
  onPortfolioFilesChange: (files: File[]) => void;
  onInstitutionalFilesChange: (files: File[]) => void;
  onSearchCompanies: () => void;
  onSelectExistingCompany: (companyId: number) => void;
  onRemoveSource: (key: "website" | "portfolio" | "institutional") => void;
  onReprocessSource: (key: "website" | "portfolio" | "institutional") => void;
};

function renderFiles(files: File[]) {
  if (files.length === 0) {
    return <p style={{ color: "#777", margin: 0 }}>Nenhum ficheiro selecionado.</p>;
  }

  return (
    <ul style={{ margin: "10px 0 0", paddingLeft: "18px", color: "#555" }}>
      {files.map((file) => (
        <li key={`${file.name}-${file.size}`}>{file.name}</li>
      ))}
    </ul>
  );
}

function renderFileMeta(files: CompanyOnboardingFileMeta[]) {
  if (files.length === 0) return null;

  return (
    <ul style={{ margin: "10px 0 0", paddingLeft: "18px", color: "#555" }}>
      {files.map((file) => (
        <li key={`${file.name}-${file.size}-${file.lastModified}`}>
          {file.name}
        </li>
      ))}
    </ul>
  );
}

function StatusBadge({ status }: { status: CompanySourceStatus }) {
  const labels: Record<CompanySourceStatus["status"], string> = {
    not_added: "Não adicionado",
    processing: "A processar",
    processed: "Processado",
    partial: "Processado parcialmente",
    no_results: "Sem resultados",
    error: "Erro",
  };

  const colors: Record<CompanySourceStatus["status"], string> = {
    not_added: "#777",
    processing: "#607b43",
    processed: "#4f6f2d",
    partial: "#8a6d1d",
    no_results: "#777",
    error: "#9f3a3a",
  };

  return (
    <li style={{ color: colors[status.status] }}>
      <strong>{status.label}:</strong> {labels[status.status]}
      {status.detail ? ` — ${status.detail}` : ""}
    </li>
  );
}

function SourceCard({
  icon,
  title,
  status,
  children,
  onReprocess,
  onRemove,
}: {
  icon: ReactNode;
  title: string;
  status?: CompanySourceStatus;
  children: ReactNode;
  onReprocess: () => void;
  onRemove: () => void;
}) {
  return (
    <div
      style={{
        display: "grid",
        gap: "12px",
        padding: "16px",
        borderRadius: "12px",
        border: "1px solid #e6e3d7",
        background: "#fff",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        {icon}
        <strong>{title}</strong>
      </div>
      {children}
      {status && (
        <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "13px" }}>
          <StatusBadge status={status} />
        </ul>
      )}
      <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
        <button
          className="onboarding-btn secondary"
          type="button"
          onClick={onReprocess}
          disabled={!status || status.status === "not_added" || status.status === "processing"}
        >
          <RefreshCw size={15} />
          Reprocessar
        </button>
        <button
          className="onboarding-btn secondary"
          type="button"
          onClick={onRemove}
          disabled={!status || status.status === "not_added" || status.status === "processing"}
        >
          <Trash2 size={15} />
          Remover
        </button>
      </div>
    </div>
  );
}

export default function CompanySourceStep({
  companyName,
  website,
  companyChoice,
  profilePath,
  portfolioFiles,
  institutionalFiles,
  portfolioFileMeta,
  institutionalFileMeta,
  searchResults,
  searchLoading,
  searchError,
  selectedExistingCompanyId,
  sourceStatuses,
  hasExistingCompany,
  onCompanyNameChange,
  onWebsiteChange,
  onCompanyChoiceChange,
  onProfilePathChange,
  onPortfolioFilesChange,
  onInstitutionalFilesChange,
  onSearchCompanies,
  onSelectExistingCompany,
  onRemoveSource,
  onReprocessSource,
}: Props) {
  const websiteStatus = sourceStatuses.find((status) => status.key === "website");
  const portfolioStatus = sourceStatuses.find(
    (status) => status.key === "portfolio",
  );
  const institutionalStatus = sourceStatuses.find(
    (status) => status.key === "institutional",
  );
  const isDevelopment = process.env.NODE_ENV === "development";

  return (
    <div className="onboarding-step">
      <h2>Vamos conhecer a sua empresa</h2>
      <p>
        Começamos por confirmar se está a criar uma empresa nova ou a tentar
        encontrar uma empresa já existente. A associação nunca é automática.
      </p>

      <div className="onboarding-form">
        <div className="profile-field">
          <label>
            <Building2 size={15} />
            Nome da empresa
          </label>
          <input
            type="text"
            placeholder="Ex.: CNLL"
            value={companyName}
            onChange={(event) => onCompanyNameChange(event.target.value)}
          />
        </div>

        <div className="profile-field">
          <label>
            <Globe size={15} />
            Website da empresa
          </label>
          <input
            type="url"
            placeholder="https://..."
            value={website}
            onChange={(event) => onWebsiteChange(event.target.value)}
          />
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: "12px",
          }}
        >
          <button
            type="button"
            className={`onboarding-choice ${companyChoice === "new" ? "active" : ""}`}
            onClick={() => onCompanyChoiceChange("new")}
          >
            <Building2 size={18} />
            Criar empresa nova
          </button>
          <button
            type="button"
            className={`onboarding-choice ${companyChoice === "existing" ? "active" : ""}`}
            onClick={() => onCompanyChoiceChange("existing")}
            disabled={hasExistingCompany}
          >
            <Search size={18} />
            Procurar empresa existente
          </button>
        </div>

        {hasExistingCompany && (
          <div
            style={{
              padding: "12px 14px",
              borderRadius: "12px",
              background: "#fafaf7",
              border: "1px solid #ecece5",
              color: "#666",
              fontSize: "13px",
            }}
          >
            Já existe uma empresa associada à sua conta. Esta experiência vai
            trabalhar sobre essa empresa.
          </div>
        )}

        {companyChoice === "existing" && !hasExistingCompany && (
          <div
            style={{
              display: "grid",
              gap: "12px",
              padding: "14px",
              borderRadius: "14px",
              background: "#fafaf7",
              border: "1px solid #ecece5",
            }}
          >
            <button
              type="button"
              className="onboarding-btn secondary"
              onClick={onSearchCompanies}
              disabled={searchLoading || (!companyName.trim() && !website.trim())}
            >
              <Search size={16} />
              {searchLoading ? "A procurar..." : "Procurar possíveis empresas"}
            </button>

            {searchError && (
              <p style={{ margin: 0, color: "#9f3a3a" }}>{searchError}</p>
            )}

            {searchResults.length > 0 && (
              <div style={{ display: "grid", gap: "10px" }}>
                {searchResults.map((result) => (
                  <div
                    key={result.id}
                    style={{
                      display: "grid",
                      gap: "6px",
                      padding: "12px",
                      borderRadius: "12px",
                      border: "1px solid #e6e3d7",
                      background: "white",
                    }}
                  >
                    <strong>{result.name}</strong>
                    <span style={{ color: "#777", fontSize: "13px" }}>
                      {result.website || "Sem website público"}
                    </span>
                    <button
                      type="button"
                      className="onboarding-btn secondary"
                      onClick={() => onSelectExistingCompany(result.id)}
                    >
                      Esta é a minha empresa
                    </button>
                    {selectedExistingCompanyId === result.id && (
                      <p style={{ margin: 0, color: "#777", fontSize: "13px" }}>
                        Para proteger dados privados, esta versão não associa
                        automaticamente. Será necessário convite ou aprovação
                        do owner/admin.
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}

            <button
              type="button"
              className="onboarding-btn secondary"
              onClick={() => onCompanyChoiceChange("new")}
            >
              Criar uma empresa diferente
            </button>
          </div>
        )}

        <div>
          <p style={{ margin: "8px 0 10px", color: "#555", fontWeight: 600 }}>
            Como pretende criar o perfil da empresa?
          </p>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: "12px",
            }}
          >
            <button
              type="button"
              className={`onboarding-choice ${profilePath === "import" ? "active" : ""}`}
              onClick={() => onProfilePathChange("import")}
            >
              <Sparkles size={18} />
              Importar informação
            </button>
            <button
              type="button"
              className={`onboarding-choice ${profilePath === "manual" ? "active" : ""}`}
              onClick={() => onProfilePathChange("manual")}
            >
              <UserRoundPen size={18} />
              Criar manualmente
            </button>
          </div>
        </div>

        {profilePath === "import" && (
          <>
            <SourceCard
              icon={<Globe size={18} />}
              title="Website"
              status={websiteStatus}
              onReprocess={() => onReprocessSource("website")}
              onRemove={() => onRemoveSource("website")}
            >
              <div className="profile-field" style={{ margin: 0 }}>
                <label>URL do website</label>
                <input
                  type="url"
                  placeholder="https://..."
                  value={website}
                  onChange={(event) => onWebsiteChange(event.target.value)}
                />
              </div>
            </SourceCard>

            <SourceCard
              icon={<FileUp size={18} />}
              title="Portfolio"
              status={portfolioStatus}
              onReprocess={() => onReprocessSource("portfolio")}
              onRemove={() => onRemoveSource("portfolio")}
            >
              <div className="profile-field" style={{ margin: 0 }}>
                <label>
                  {portfolioStatus?.status === "processed" ||
                  portfolioStatus?.status === "partial"
                    ? "Substituir ficheiro"
                    : "Selecionar PDF"}
                </label>
                <input
                  type="file"
                  accept=".pdf,.txt,.md,.html,.htm"
                  multiple
                  onChange={(event) =>
                    onPortfolioFilesChange(Array.from(event.target.files ?? []))
                  }
                />
                <div style={{ marginTop: "8px" }}>
                  {portfolioFiles.length
                    ? renderFiles(portfolioFiles)
                    : renderFileMeta(portfolioFileMeta) || (
                        <p style={{ color: "#777", margin: 0 }}>
                          Sem portfolio carregado.
                        </p>
                      )}
                </div>
              </div>
            </SourceCard>

            <SourceCard
              icon={<FileText size={18} />}
              title="Documentos institucionais"
              status={institutionalStatus}
              onReprocess={() => onReprocessSource("institutional")}
              onRemove={() => onRemoveSource("institutional")}
            >
              <div className="profile-field" style={{ margin: 0 }}>
                <label>Adicionar documentos</label>
                <input
                  type="file"
                  accept=".pdf,.txt,.md,.html,.htm"
                  multiple
                  onChange={(event) =>
                    onInstitutionalFilesChange(
                      Array.from(event.target.files ?? []),
                    )
                  }
                />
                <div style={{ marginTop: "8px" }}>
                  {institutionalFiles.length
                    ? renderFiles(institutionalFiles)
                    : renderFileMeta(institutionalFileMeta) || (
                        <p style={{ color: "#777", margin: 0 }}>
                          Sem documentos carregados.
                        </p>
                      )}
                </div>
              </div>
            </SourceCard>

            {isDevelopment && websiteStatus?.status !== "not_added" && (
              <div className="profile-field">
                <label>Dados encontrados no website</label>
                <ul style={{ margin: 0, paddingLeft: "18px", color: "#444" }}>
                  <li>Páginas visitadas: {websiteStatus?.pages_visited ?? 0}</li>
                  <li>
                    Serviços: {(websiteStatus?.services_found ?? []).join(", ") || "Sem dados"}
                  </li>
                  <li>
                    Competências: {(websiteStatus?.competences_found ?? []).join(", ") || "Sem dados"}
                  </li>
                  <li>Projetos: {websiteStatus?.projects_found ?? 0}</li>
                  <li>Factos criados: {websiteStatus?.facts_created ?? 0}</li>
                  <li>
                    Avisos: {(websiteStatus?.warnings ?? []).join(", ") || "Sem avisos"}
                  </li>
                </ul>
              </div>
            )}
          </>
        )}

        {profilePath === "manual" && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              color: "#777",
              fontSize: "13px",
              padding: "12px 14px",
              borderRadius: "12px",
              background: "#fafaf7",
              border: "1px solid #ecece5",
            }}
          >
            <Link2 size={16} />
            Vai avançar diretamente para a entrevista existente do backend.
          </div>
        )}
      </div>
    </div>
  );
}
