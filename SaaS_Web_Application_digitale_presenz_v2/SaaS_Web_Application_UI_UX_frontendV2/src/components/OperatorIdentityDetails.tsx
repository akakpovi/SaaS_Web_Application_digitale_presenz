import type { ReactNode } from "react"
import { useI18n } from "../i18n"
import {
  operatorAddressLines,
  operatorDisplayName,
  operatorValue,
} from "../config/operator"

/**
 * The operator's legal details, rendered from the single source in
 * `config/operator.json`.
 *
 * Render it only when `isOperatorIdentityComplete()` is true: until the values
 * exist, the legal pages say the provider is named in the imprint instead of
 * showing an empty box, and the imprint shows marked placeholders. The
 * `address` variant keeps the block to the recipient details a withdrawal
 * declaration needs; `full` adds register, VAT ID and DPO when they exist.
 */
interface Props {
  variant?: "full" | "address"
}

function DetailsRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid sm:grid-cols-3 gap-2 px-4 py-3">
      <dt className="text-sm font-medium text-slate-600">{label}</dt>
      <dd className="sm:col-span-2 text-sm text-slate-900 break-words">
        {children}
      </dd>
    </div>
  )
}

export default function OperatorIdentityDetails({ variant = "full" }: Props) {
  const { t } = useI18n()

  const name = operatorDisplayName()
  const addressLines = operatorAddressLines()
  const email = operatorValue("email")
  const register =
    variant === "full"
      ? [operatorValue("registerCourt"), operatorValue("registerNumber")]
          .filter((part): part is string => part !== null)
          .join(" · ")
      : ""
  const vatId = variant === "full" ? operatorValue("vatId") : null
  const dpo = variant === "full" ? operatorValue("dataProtectionOfficer") : null

  return (
    <dl className="mt-4 divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden">
      {name && (
        <DetailsRow label={t("legal.providerTitle")}>{name}</DetailsRow>
      )}
      {addressLines.length > 0 && (
        <DetailsRow label={t("legal.contactTitle")}>
          <span className="whitespace-pre-line">{addressLines.join("\n")}</span>
        </DetailsRow>
      )}
      {email && (
        <DetailsRow label={t("common.email")}>
          <a href={`mailto:${email}`} className="text-indigo-600 hover:underline">
            {email}
          </a>
        </DetailsRow>
      )}
      {register && (
        <DetailsRow label={t("legal.registerTitle")}>{register}</DetailsRow>
      )}
      {vatId && (
        <DetailsRow label={t("legal.vatIdTitle")}>{vatId}</DetailsRow>
      )}
      {dpo && (
        <DetailsRow label={t("legal.dpoTitle")}>{dpo}</DetailsRow>
      )}
    </dl>
  )
}
