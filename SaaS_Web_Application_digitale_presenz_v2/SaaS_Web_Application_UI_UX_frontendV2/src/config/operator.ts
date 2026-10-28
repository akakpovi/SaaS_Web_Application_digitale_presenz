/**
 * Single source of truth for the operator (Anbieter) identity.
 *
 * Every legal page — imprint, privacy policy, terms and withdrawal — renders
 * its identity values from `operator.json` through this module, so filling the
 * real data once updates all of them consistently. The values are content, not
 * configuration: they are reviewed in Git like the legal text itself, which is
 * why they live in a data file next to the pages instead of in environment
 * variables (`.env.example` documents deployment configuration only).
 *
 * Three states are kept apart on purpose, because confusing them is a legal
 * defect rather than a cosmetic one:
 *   - `provided`      — a real, verified value; rendered as-is.
 *   - `missing`       — not known yet; rendered as a clearly marked placeholder
 *                       (never replaced by an invented value).
 *   - `not-applicable`— legally not applicable for this operator; the row is
 *                       omitted, the documented reason stays for the audit.
 *
 * `scripts/check-operator-identity.mjs` validates the data file (schema,
 * placeholder leaks, missing i18n keys, launch gate) and the E2E spec
 * `e2e/operator-identity.spec.ts` verifies the rendered pages.
 */
import raw from "./operator.json"
import type { MessageKey } from "../i18n"

export type OperatorRequirement = "mandatory" | "conditional" | "optional"
export type OperatorFieldStatus = "provided" | "missing" | "not-applicable"

/** Field keys of `operator.json`; `_…` entries are documentation, not fields. */
export type OperatorFieldKey = Exclude<keyof typeof raw, `_${string}`>

interface RawOperatorField {
  requirement: OperatorRequirement
  condition?: string
  usedOn: readonly string[]
  labelKey: string
  placeholderKey?: string
  value?: string | null
  notApplicable?: string | null
}

export interface OperatorField {
  key: OperatorFieldKey
  requirement: OperatorRequirement
  /** Why a conditional field can be absent — shown in the audit inventory. */
  condition: string | null
  /** Pages that render this value, for the missing-information report. */
  usedOn: readonly string[]
  labelKey: MessageKey
  /**
   * Localised placeholder for a missing value, or `null` when a missing value
   * must not be advertised (optional fields without a placeholder key).
   */
  placeholderKey: MessageKey | null
  status: OperatorFieldStatus
  value: string | null
  notApplicableReason: string | null
}

function nonEmpty(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null
}

function toField(key: OperatorFieldKey, rawField: RawOperatorField): OperatorField {
  const value = nonEmpty(rawField.value)
  const notApplicableReason = nonEmpty(rawField.notApplicable)

  const status: OperatorFieldStatus = value
    ? "provided"
    : notApplicableReason
      ? "not-applicable"
      : "missing"

  return {
    key,
    requirement: rawField.requirement,
    condition: nonEmpty(rawField.condition),
    usedOn: rawField.usedOn,
    labelKey: rawField.labelKey as MessageKey,
    placeholderKey: (nonEmpty(rawField.placeholderKey) as MessageKey | null) ?? null,
    status,
    value,
    notApplicableReason,
  }
}

/** Field order follows `operator.json`, which is also the imprint row order. */
export const OPERATOR_FIELDS: readonly OperatorField[] = Object.entries(
  raw as unknown as Record<string, RawOperatorField>,
)
  .filter(([key]) => !key.startsWith("_"))
  .map(([key, field]) => toField(key as OperatorFieldKey, field))

function field(key: OperatorFieldKey): OperatorField {
  const match = OPERATOR_FIELDS.find((entry) => entry.key === key)
  if (!match) throw new Error(`unknown operator field "${key}"`)
  return match
}

/** The value of one field, or `null` while it is missing or not applicable. */
export function operatorValue(key: OperatorFieldKey): string | null {
  return field(key).value
}

/** Legal name incl. the legal form when both are known, else `null`. */
export function operatorDisplayName(): string | null {
  const name = operatorValue("legalName")
  if (!name) return null
  const form = operatorValue("legalForm")
  return form ? `${name} ${form}` : name
}

/** Postal address lines in the order a German address is written. */
export function operatorAddressLines(): string[] {
  return (["street", "postalCity", "country"] as const)
    .map((key) => operatorValue(key))
    .filter((line): line is string => line !== null)
}

/**
 * Imprint rows: provided values, plus every missing value that carries a
 * placeholder. Not-applicable fields disappear, and a missing optional value
 * stays quiet instead of pretending to be required.
 */
export function operatorImpressumRows(): readonly OperatorField[] {
  return OPERATOR_FIELDS.filter(
    (entry) =>
      entry.status === "provided" ||
      (entry.status === "missing" && entry.placeholderKey !== null),
  )
}

/** Every field without a value yet — the operator's to-do list. */
export function missingOperatorFields(): readonly OperatorField[] {
  return OPERATOR_FIELDS.filter((entry) => entry.status === "missing")
}

/** True while any placeholder is rendered, so the warning band stays visible. */
export function hasUnresolvedPlaceholders(): boolean {
  return operatorImpressumRows().some((entry) => entry.status === "missing")
}

/**
 * The identity is complete once every mandatory field is provided. Conditional
 * fields may legitimately stay `missing` or become `not-applicable` — they are
 * open decisions, not blockers, and are reported separately.
 */
export function isOperatorIdentityComplete(): boolean {
  return OPERATOR_FIELDS.every(
    (entry) => entry.requirement !== "mandatory" || entry.status === "provided",
  )
}
