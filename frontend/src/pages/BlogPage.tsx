import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Clock } from "lucide-react";
import SEO from "../components/SEO";

const articles = [
  {
    slug: "what-is-website-monitoring",
    title: "What is website monitoring?",
    description: "A plain-language guide to website monitoring — what it is, why it matters, and how it works.",
    date: "2026-08-15",
    readTime: "5 min",
    category: "Guides",
  },
  {
    slug: "how-to-monitor-website-uptime",
    title: "How to monitor your website uptime",
    description: "Learn how uptime monitoring works and why tracking availability matters for your business.",
    date: "2026-08-10",
    readTime: "4 min",
    category: "Guides",
  },
  {
    slug: "what-is-dmarc",
    title: "What is DMARC and why does it matter for small businesses?",
    description: "DMARC protects your domain from email spoofing. Here's what it is and how to set it up.",
    date: "2026-08-05",
    readTime: "6 min",
    category: "Email security",
  },
  {
    slug: "how-to-check-ssl-certificate",
    title: "How to check your SSL certificate",
    description: "An SSL certificate ensures your website is trusted. Here's how to check it and what to do if it expires.",
    date: "2026-07-28",
    readTime: "4 min",
    category: "SSL",
  },
  {
    slug: "website-security-checklist-small-business",
    title: "Website security checklist for small businesses",
    description: "A practical checklist covering SSL, DNS, email security, security headers and more — without the technical jargon.",
    date: "2026-07-20",
    readTime: "8 min",
    category: "Security",
  },
  {
    slug: "digital-presence-checklist-small-business",
    title: "Digital presence checklist for small businesses",
    description: "Everything a small business needs to monitor and protect their digital presence in 2026.",
    date: "2026-07-12",
    readTime: "7 min",
    category: "Strategy",
  },
];

export function BlogPage() {
  return (
    <div className="min-h-full bg-white">
      <SEO
        title="Website Monitoring Blog | Presence"
        description="Plain-language guides on website monitoring, SSL, DNS, email security, uptime and digital presence for small businesses."
        path="/blog"
      />

      {/* Nav */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between gap-6">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">P</span>
            </div>
            <span className="font-bold text-slate-900">Presence</span>
          </Link>
          <nav className="hidden md:flex items-center gap-5 text-sm text-slate-600">
            <Link to="/#features" className="hover:text-slate-900">Features</Link>
            <Link to="/pricing" className="hover:text-slate-900">Pricing</Link>
            <Link to="/blog" className="hover:text-slate-900">Blog</Link>
          </nav>
          <Link to="/register"><button className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700">Get started</button></Link>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-16">
        <div className="mb-12">
          <p className="text-xs font-bold uppercase tracking-widest text-indigo-600 mb-3">Blog</p>
          <h1 className="text-4xl font-bold text-slate-900 mb-4">Digital presence guides for small businesses</h1>
          <p className="text-lg text-slate-500">Plain-language articles on website monitoring, SSL, DNS, email security, and everything else that affects your digital presence.</p>
        </div>

        <div className="grid md:grid-cols-2 gap-6">
          {articles.map((article) => (
            <article key={article.slug} className="group">
              <Link to={`/blog/${article.slug}`}>
                <div className="border border-slate-200 rounded-2xl p-6 h-full hover:border-indigo-200 hover:shadow-md transition-all duration-200 flex flex-col">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="px-2.5 py-1 bg-indigo-50 text-indigo-700 text-xs font-medium rounded-full">{article.category}</span>
                    <span className="flex items-center gap-1 text-xs text-slate-400">
                      <Clock size={11} /> {article.readTime} read
                    </span>
                  </div>
                  <h2 className="text-lg font-bold text-slate-900 mb-2 group-hover:text-indigo-700 transition-colors leading-snug">{article.title}</h2>
                  <p className="text-sm text-slate-500 flex-1 leading-relaxed">{article.description}</p>
                  <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-100">
                    <time dateTime={article.date} className="text-xs text-slate-400">
                      {new Date(article.date).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}
                    </time>
                    <span className="text-xs font-medium text-indigo-600 flex items-center gap-1 group-hover:gap-2 transition-all">Read article <ArrowRight size={12} /></span>
                  </div>
                </div>
              </Link>
            </article>
          ))}
        </div>

        {/* CTA */}
        <div className="mt-16 p-8 bg-indigo-600 rounded-2xl text-center text-white">
          <h2 className="text-2xl font-bold mb-3">Check your website for free</h2>
          <p className="text-indigo-200 mb-6">See your website health score in seconds. No account required.</p>
          <Link to="/">
            <button className="px-6 py-3 bg-white text-indigo-700 font-semibold rounded-xl hover:bg-indigo-50 transition-colors">
              Check my website
            </button>
          </Link>
        </div>
      </main>

      <footer className="border-t border-slate-200 py-8 px-4 text-center mt-8">
        <p className="text-sm text-slate-400">© 2026 Presence — <Link to="/" className="hover:text-slate-600">Home</Link> · <Link to="/pricing" className="hover:text-slate-600">Pricing</Link></p>
      </footer>
    </div>
  );
}
