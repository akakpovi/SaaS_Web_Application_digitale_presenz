import { AlertTriangle } from "lucide-react"
import { useI18n } from "../i18n"

/**
 * Marks a legal page as an unvalidated draft.
 *
 * Presence ships legal drafts that were written for the product, not by a
 * lawyer. Publishing them as if they were reviewed would misrepresent the
 * compliance status, so every such page carries this banner plus the concrete
 * list of points a qualified person has to settle before the German launch.
 */
export default function LegalReviewNotice() {
  const { t, tList } = useI18n()

  return (
    <div className="mb-10 rounded-xl border border-amber-300 bg-amber-50 p-5">
      <div className="flex items-start gap-3">
        <AlertTriangle size={16} className="text-amber-500 flex-shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold text-amber-900 text-sm mb-1">
            {t("legal.reviewNoticeTitle")}
          </p>
          <p className="text-sm text-amber-900 leading-relaxed">
            {t("legal.reviewNoticeBody")}
          </p>
        </div>
      </div>
      <ul className="mt-4 space-y-2 text-sm text-amber-900">
        {tList("legal.reviewChecklist").map((item) => (
          <li key={item} className="flex items-start gap-2">
            <span
              aria-hidden="true"
              className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-amber-500"
            />
            <span className="leading-relaxed">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
