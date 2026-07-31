"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Check,
  MessageSquareText,
  Pencil,
  Send,
  Slash,
} from "lucide-react";
import type {
  CompanyInterviewAnswerValue,
  CompanyInterviewQuestion,
  CompanyInterviewQuestionType,
} from "./company-types";

type Props = {
  sessionId: number | null;
  questions: CompanyInterviewQuestion[];
  answers: Record<number, CompanyInterviewAnswerValue>;
  submittingQuestionId: number | null;
  loading: boolean;
  onAnswerChange: (
    questionId: number,
    value: CompanyInterviewAnswerValue,
  ) => void;
  onSubmitAnswer: (
    question: CompanyInterviewQuestion,
    answer: CompanyInterviewAnswerValue,
  ) => void;
};

function getQuestionType(
  question: CompanyInterviewQuestion,
): CompanyInterviewQuestionType {
  return (
    question.type ||
    question.question_type ||
    (question.question_source === "validation"
      ? "boolean_confirmation"
      : "free_text")
  );
}

function renderSource(question: CompanyInterviewQuestion): string {
  const source = String(question.source || "").trim();
  if (!source) {
    return question.question_source === "validation"
      ? "Validação"
      : "Descoberta";
  }

  const lower = source.toLowerCase();
  if (lower.startsWith("website")) return "Website";
  if (lower.startsWith("portfolio")) return "Portfólio";
  if (lower.startsWith("document")) return "Documento";
  return source;
}

export default function CompanyInterviewStep({
  sessionId,
  questions,
  answers,
  submittingQuestionId,
  loading,
  onAnswerChange,
  onSubmitAnswer,
}: Props) {
  const [correctionQuestionId, setCorrectionQuestionId] = useState<number | null>(
    null,
  );
  const [correctionText, setCorrectionText] = useState("");

  const activeQuestion = useMemo(
    () => questions[0],
    [questions],
  );

  useEffect(() => {
    if (correctionQuestionId === activeQuestion?.id) return;
    setCorrectionQuestionId(null);
    setCorrectionText("");
  }, [activeQuestion?.id, correctionQuestionId]);

  function submitBoolean(question: CompanyInterviewQuestion, value: boolean | null) {
    const payload =
      value === null
        ? { answer: null, certainty: "unknown" }
        : value;
    onAnswerChange(question.id, payload);
    onSubmitAnswer(question, payload);
  }

  function submitSingleChoice(
    question: CompanyInterviewQuestion,
    value: string,
  ) {
    onAnswerChange(question.id, value);
    onSubmitAnswer(question, value);
  }

  function submitMultiChoice(question: CompanyInterviewQuestion) {
    const current = answers[question.id];
    const normalized = Array.isArray(current) ? current : [];
    onSubmitAnswer(question, normalized);
  }

  function toggleMultiChoiceValue(
    question: CompanyInterviewQuestion,
    value: string,
  ) {
    const current = answers[question.id];
    const list = Array.isArray(current) ? [...current] : [];
    const next = list.includes(value)
      ? list.filter((item) => item !== value)
      : [...list, value];
    onAnswerChange(question.id, next);
  }

  function renderQuestionBody(question: CompanyInterviewQuestion) {
    const type = getQuestionType(question);
    const current = answers[question.id];
    const valueText = typeof current === "string" ? current : "";

    if (type === "boolean_confirmation") {
      return (
        <div style={{ display: "grid", gap: "12px" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
              gap: "10px",
            }}
          >
            <button
              type="button"
              className="onboarding-btn primary"
              onClick={() => submitBoolean(question, true)}
              disabled={submittingQuestionId === question.id}
            >
              <Check size={18} />
              Sim
            </button>
            <button
              type="button"
              className="onboarding-btn secondary"
              onClick={() => submitBoolean(question, false)}
              disabled={submittingQuestionId === question.id}
            >
              <Slash size={18} />
              Não
            </button>
            <button
              type="button"
              className="onboarding-btn secondary"
              onClick={() => submitBoolean(question, null)}
              disabled={submittingQuestionId === question.id}
            >
              Não tenho a certeza
            </button>
            <button
              type="button"
              className="onboarding-btn secondary"
              onClick={() => {
                setCorrectionQuestionId(question.id);
                setCorrectionText(valueText);
              }}
            >
              <Pencil size={18} />
              Corrigir
            </button>
          </div>

          {correctionQuestionId === question.id && (
            <div
              style={{
                display: "grid",
                gap: "10px",
                padding: "12px",
                borderRadius: "14px",
                background: "#fafaf7",
                border: "1px solid #ecece5",
              }}
            >
              <input
                className="profile-field"
                type="text"
                placeholder="Escreva a correção curta"
                value={correctionText}
                onChange={(event) => {
                  setCorrectionText(event.target.value);
                  onAnswerChange(question.id, event.target.value);
                }}
              />
              <button
                type="button"
                className="onboarding-btn primary"
                onClick={() => {
                  const trimmed = correctionText.trim();
                  if (!trimmed) return;
                  onAnswerChange(question.id, trimmed);
                  onSubmitAnswer(question, trimmed);
                }}
                disabled={submittingQuestionId === question.id}
              >
                <Send size={16} />
                Guardar correção
              </button>
            </div>
          )}
        </div>
      );
    }

    if (type === "single_choice") {
      return (
        <div style={{ display: "grid", gap: "12px" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
              gap: "10px",
            }}
          >
            {(question.options || []).map((option) => (
              <button
                key={option.value}
                type="button"
                className={`onboarding-choice ${current === option.value ? "active" : ""}`}
                onClick={() => submitSingleChoice(question, option.value)}
                disabled={submittingQuestionId === question.id}
              >
                {option.label}
              </button>
            ))}
          </div>
          <p style={{ margin: 0, color: "#777", fontSize: "13px" }}>
            Seleção única. A escolha avança automaticamente para a próxima pergunta.
          </p>
        </div>
      );
    }

    if (type === "multi_choice") {
      const selected = Array.isArray(current) ? current : [];
      return (
        <div style={{ display: "grid", gap: "12px" }}>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "10px",
            }}
          >
            {(question.options || []).map((option) => (
              <button
                key={option.value}
                type="button"
                className={`onboarding-choice ${selected.includes(option.value) ? "active" : ""}`}
                onClick={() => toggleMultiChoiceValue(question, option.value)}
                disabled={submittingQuestionId === question.id}
                style={{ minWidth: "140px" }}
              >
                {option.label}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="onboarding-btn primary"
            onClick={() => submitMultiChoice(question)}
            disabled={submittingQuestionId === question.id || selected.length === 0}
            style={{ width: "fit-content" }}
          >
            <Check size={16} />
            Guardar seleção
          </button>
        </div>
      );
    }

    return (
      <div style={{ display: "grid", gap: "12px" }}>
        <textarea
          className="profile-field"
          style={{
            width: "100%",
            minHeight: "120px",
            resize: "vertical",
            borderRadius: "14px",
            border: "1px solid #ddd",
            padding: "12px 14px",
            background: "#fff",
          }}
          placeholder="Escreva uma resposta curta e objetiva..."
          value={valueText}
          onChange={(event) => onAnswerChange(question.id, event.target.value)}
        />
        <button
          type="button"
          className="onboarding-btn primary"
          onClick={() => onSubmitAnswer(question, valueText)}
          disabled={submittingQuestionId === question.id || !valueText.trim()}
          style={{ width: "fit-content" }}
        >
          <Send size={16} />
          Guardar resposta
        </button>
      </div>
    );
  }

  return (
    <div className="onboarding-step">
      <h2>Entrevista AI</h2>
      <p>
        Vamos confirmar rapidamente os factos extraídos e preencher apenas o
        que ainda está em falta.
      </p>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          color: "#777",
          marginBottom: "18px",
          padding: "12px 14px",
          borderRadius: "12px",
          background: "#fafaf7",
          border: "1px solid #ecece5",
        }}
      >
        <MessageSquareText size={16} />
        {sessionId
          ? `Sessão ativa #${sessionId} com ${questions.length} pergunta(s) por responder.`
          : "A carregar sessão de entrevista..."}
      </div>

      {loading ? (
        <p style={{ color: "#777" }}>A carregar perguntas...</p>
      ) : questions.length === 0 ? (
        <div
          style={{
            padding: "18px",
            borderRadius: "14px",
            border: "1px dashed #ddd",
            background: "#fafaf7",
            color: "#666",
          }}
        >
          Ainda não existem perguntas pendentes. Podes avançar para o resumo.
        </div>
      ) : activeQuestion ? (
        <article
          style={{
            padding: "18px",
            borderRadius: "18px",
            border: "1px solid #e7e7e0",
            background: "white",
            display: "grid",
            gap: "14px",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: "12px",
              flexWrap: "wrap",
              alignItems: "flex-start",
            }}
          >
            <div style={{ display: "grid", gap: "6px" }}>
              <strong style={{ fontSize: "18px", lineHeight: 1.35 }}>
                {activeQuestion.question}
              </strong>
              {activeQuestion.evidence ? (
                <p
                  style={{
                    margin: 0,
                    color: "#666",
                    fontSize: "13px",
                    lineHeight: 1.5,
                  }}
                >
                  {activeQuestion.evidence}
                </p>
              ) : null}
            </div>

            <span
              style={{
                fontSize: "11px",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: "#8a8a82",
                background: "#fafaf7",
                border: "1px solid #ecece5",
                borderRadius: "999px",
                padding: "5px 8px",
                height: "fit-content",
              }}
            >
              {renderSource(activeQuestion)}
            </span>
          </div>

          {activeQuestion.reason ? (
            <p style={{ margin: 0, color: "#777", fontSize: "13px" }}>
              {activeQuestion.reason}
            </p>
          ) : null}

          {typeof activeQuestion.confidence === "number" ? (
            <p style={{ margin: 0, color: "#777", fontSize: "13px" }}>
              Confiança estimada: {Math.round(activeQuestion.confidence * 100)}%
            </p>
          ) : null}

          {renderQuestionBody(activeQuestion)}
        </article>
      ) : null}

      {questions.length > 1 && activeQuestion ? (
        <p style={{ color: "#777", fontSize: "13px", marginTop: "12px" }}>
          Restam {questions.length - 1} pergunta(s) depois desta.
        </p>
      ) : null}
    </div>
  );
}
