import test from "node:test";
import assert from "node:assert/strict";
import {
  EMPTY,
  buildFunctionalProgramViewModel,
} from "../src/components/analise/functionalProgramModel.js";

test("prioritizes explicit global areas over generic area candidates", () => {
  const viewModel = buildFunctionalProgramViewModel({
    functionalProgram: {
      areas: [
        { label: "Área 1", value: "999 m²" },
        { label: "Área total", value: "12 500 m²" },
      ],
      main_spaces: ["Biblioteca", "Salas de aula"],
      requirements: ["Acessibilidade universal"],
      constraints: ["Intervenção limitada ao perímetro"],
      summary: "Síntese curta do programa",
    },
    extraction: {
      facts: {
        area_total: { value: "12 500 m²" },
        area_bruta: { value: "13 200 m²" },
        area_intervencao: { value: "11 300 m²" },
        area_util: { value: "8 500 m²" },
      },
    },
  });

  assert.equal(viewModel.metrics[0].value, "12 500 m²");
  assert.equal(viewModel.metrics[1].value, "13 200 m²");
  assert.equal(viewModel.metrics[2].value, "11 300 m²");
  assert.equal(viewModel.metrics[3].value, "8 500 m²");
  assert.equal(viewModel.previewSections[0].items[0], "Área total — 12 500 m²");
  assert.ok(viewModel.modalSections.some((section) => section.key === "areas"));
});

test('falls back to "Por confirmar" when no data exists', () => {
  const viewModel = buildFunctionalProgramViewModel({});
  assert.equal(viewModel.metrics[0].value, EMPTY);
  assert.equal(viewModel.metrics[1].value, EMPTY);
  assert.equal(viewModel.metrics[2].value, EMPTY);
  assert.equal(viewModel.metrics[3].value, EMPTY);
  assert.equal(viewModel.summary, EMPTY);
  assert.equal(viewModel.previewSections[0].empty, EMPTY);
});

