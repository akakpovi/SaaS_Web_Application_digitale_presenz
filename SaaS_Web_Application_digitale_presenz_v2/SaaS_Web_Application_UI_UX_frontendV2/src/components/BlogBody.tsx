import DOMPurify from "dompurify"

/**
 * Rend le HTML du CMS après assainissement.
 *
 * Le contenu WordPress est éditorial mais reste une entrée non fiable : un
 * éditeur compromis ne doit pas pouvoir injecter de script dans l'application.
 */
export default function BlogBody({ html }: { html: string }) {
  const clean = DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
    ADD_ATTR: ["target", "rel"],
  })

  return (
    <div
      className="prose prose-slate max-w-none text-sm leading-relaxed [&_a]:text-indigo-600 [&_a]:underline [&_h2]:mt-8 [&_h2]:mb-3 [&_h2]:text-xl [&_h2]:font-bold [&_li]:my-1 [&_p]:my-4 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-slate-100 [&_pre]:p-4 [&_ul]:list-disc [&_ul]:pl-5"
      dangerouslySetInnerHTML={{ __html: clean }}
    />
  )
}
