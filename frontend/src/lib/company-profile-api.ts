import { API_URL } from "./api";
import {
  normalizeCompanyProfile,
  type CompanyProfile,
} from "@/components/company/company-types";

const COMPANY_PROFILE_URL = `${API_URL}/company/profile`;
const COMPANY_PROFILE_TIMEOUT_MS = 25000;

function debugCompanyProfileFetch(message: string, payload: Record<string, unknown>) {
  if (process.env.NODE_ENV === "production") return;
  console.debug(message, payload);
}

async function readResponseText(response: Response): Promise<string> {
  try {
    return await response.text();
  } catch {
    return "";
  }
}

async function readJsonOrNull(response: Response): Promise<unknown> {
  const text = await readResponseText(response);
  const trimmed = text.trim();
  if (!trimmed) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return text;
  }
}

async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs = COMPANY_PROFILE_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(url, {
      ...init,
      signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timer);
  }
}

function buildTransportError(
  method: string,
  url: string,
  error: unknown,
  timeoutMs: number,
) {
  if (error instanceof DOMException && error.name === "AbortError") {
    return new Error(
      `[company-profile] ${method} ${url} timed out after ${timeoutMs}ms.`,
    );
  }

  const message =
    error instanceof Error ? error.message : String(error || "unknown error");

  if (message.toLowerCase().includes("failed to fetch")) {
    return new Error(
      `[company-profile] ${method} ${url} failed to fetch. Possible CORS/network/backend disconnect. Original error: ${message}`,
    );
  }

  return new Error(
    `[company-profile] ${method} ${url} transport error: ${message}`,
  );
}

async function verifyProfileSaved(token: string): Promise<CompanyProfile | null> {
  const response = await fetchWithTimeout(
    COMPANY_PROFILE_URL,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: "no-store",
    },
    COMPANY_PROFILE_TIMEOUT_MS,
  );

  debugCompanyProfileFetch("[company-profile] verification GET", {
    url: COMPANY_PROFILE_URL,
    method: "GET",
    status: response.status,
  });

  if (!response.ok) {
    return null;
  }

  return normalizeCompanyProfile(await readJsonOrNull(response));
}

export async function saveCompanyProfileWithDiagnostics(
  token: string,
  profile: CompanyProfile,
  hasProfile: boolean,
): Promise<CompanyProfile> {
  const method = hasProfile ? "PUT" : "POST";
  const payload = JSON.stringify(profile);

  debugCompanyProfileFetch("[company-profile] request", {
    url: COMPANY_PROFILE_URL,
    method,
    payload,
  });

  try {
    const response = await fetchWithTimeout(
      COMPANY_PROFILE_URL,
      {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: payload,
      },
      COMPANY_PROFILE_TIMEOUT_MS,
    );

    const responseText = await readResponseText(response);
    debugCompanyProfileFetch("[company-profile] response", {
      url: COMPANY_PROFILE_URL,
      method,
      status: response.status,
      body: responseText,
    });

    if (!response.ok) {
      const parsed = responseText ? (() => {
        try {
          return JSON.parse(responseText) as { detail?: string } | null;
        } catch {
          return null;
        }
      })() : null;

      throw new Error(
        parsed?.detail ||
          responseText ||
          `HTTP ${response.status} while saving the company profile.`,
      );
    }

    const parsed = responseText
      ? (() => {
          try {
            return JSON.parse(responseText);
          } catch {
            return null;
          }
        })()
      : null;

    return normalizeCompanyProfile(parsed);
  } catch (error) {
    const transportError = buildTransportError(
      method,
      COMPANY_PROFILE_URL,
      error,
      COMPANY_PROFILE_TIMEOUT_MS,
    );

    debugCompanyProfileFetch("[company-profile] transport error", {
      url: COMPANY_PROFILE_URL,
      method,
      error: transportError.message,
    });

    const verified = await verifyProfileSaved(token).catch(() => null);
    if (verified) {
      debugCompanyProfileFetch("[company-profile] recovered after save", {
        url: COMPANY_PROFILE_URL,
        method: "GET",
        status: "verified",
      });
      return verified;
    }

    throw transportError;
  }
}
