import React, { useState, useEffect } from "react";
import { Star, RefreshCw, Plus, X, ThumbsUp } from "lucide-react";
import { Card, Button } from "../components/ui";
import api from "../services/api";
import { websiteService, Website } from "../services/websiteService";

interface ReviewSource {
  id: number;
  website: number;
  provider: string;
  name: string;
  enabled: boolean;
}

interface Review {
  id: string;
  source: number;
  author_name: string;
  rating: number;
  text: string;
  sentiment: "positive" | "neutral" | "negative";
  is_approved: boolean;
  review_date: string;
}

function StarRating({ rating }: { rating: number }) {
  return (
    <div className="flex items-center gap-0.5">
      {[1,2,3,4,5].map((s) => (
        <Star key={s} size={14}
          className={s <= rating ? "text-amber-400 fill-amber-400" : "text-slate-200 fill-slate-200"} />
      ))}
    </div>
  );
}

function sentimentColor(s: string) {
  if (s === "positive") return "text-emerald-600 bg-emerald-50 border-emerald-200";
  if (s === "negative") return "text-red-600 bg-red-50 border-red-200";
  return "text-slate-600 bg-slate-50 border-slate-200";
}

function timeAgo(d: string) {
  const days = Math.floor((Date.now() - new Date(d).getTime()) / 86400000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 30) return days + "d ago";
  return new Date(d).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export default function Reviews() {
  const [websites, setWebsites]   = useState<Website[]>([]);
  const [sources, setSources]     = useState<ReviewSource[]>([]);
  const [reviews, setReviews]     = useState<Review[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError]         = useState("");
  const [showAdd, setShowAdd]     = useState(false);
  const [selectedWebsite, setSelectedWebsite] = useState<number | null>(null);
  const [newSourceName, setNewSourceName]     = useState("");
  const [adding, setAdding]       = useState(false);
  const [activeSource, setActiveSource] = useState<number | null>(null);

  const load = async () => {
    setIsLoading(true);
    setError("");
    try {
      const [sites, srcRes, revRes] = await Promise.all([
        websiteService.list(),
        api.get<{ results: ReviewSource[] }>("/reviews/sources/"),
        api.get<{ results: Review[] }>("/reviews/"),
      ]);
      setWebsites(sites);
      setSources(srcRes.data.results ?? []);
      setReviews(revRes.data.results ?? []);
      if (sites.length > 0 && !selectedWebsite) setSelectedWebsite(sites[0].id);
    } catch {
      setError("Failed to load reviews.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const loadBySource = async (sourceId: number | null) => {
    setActiveSource(sourceId);
    try {
      const params = sourceId ? "?source=" + sourceId : "";
      const res = await api.get<{ results: Review[] }>("/reviews/" + params);
      setReviews(res.data.results ?? []);
    } catch { setError("Failed to filter reviews."); }
  };

  const handleAddSource = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedWebsite) return;
    setAdding(true);
    try {
      await api.post("/reviews/sources/", {
        website: selectedWebsite,
        provider: "manual",
        name: newSourceName.trim() || "Manual reviews",
        enabled: true,
      });
      setNewSourceName("");
      setShowAdd(false);
      await load();
    } catch { setError("Failed to add source."); }
    finally { setAdding(false); }
  };

  const handleApprove = async (id: string) => {
    try {
      await api.post("/reviews/" + id + "/approve/");
      setReviews((prev) => prev.map((r) => r.id === id ? { ...r, is_approved: true } : r));
    } catch { setError("Failed to approve."); }
  };

  const avgRating = reviews.length > 0
    ? (reviews.reduce((a, r) => a + r.rating, 0) / reviews.length).toFixed(1) : "—";
  const positive = reviews.filter((r) => r.sentiment === "positive").length;
  const negative = reviews.filter((r) => r.sentiment === "negative").length;

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Reviews</h1>
          <p className="text-slate-500 mt-1">Manage your customer reviews and responses.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} disabled={isLoading} className="p-2 hover:bg-slate-100 rounded-lg transition-colors">
            <RefreshCw size={16} className={"text-slate-500 " + (isLoading ? "animate-spin" : "")} />
          </button>
          <Button onClick={() => setShowAdd(true)}><Plus size={16} /> Add source</Button>
        </div>
      </div>

      {error && <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600">{error}</div>}

      {/* Modal ajout source */}
      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowAdd(false)} />
          <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-bold text-slate-900">Add review source</h2>
              <button onClick={() => setShowAdd(false)} className="p-1.5 hover:bg-slate-100 rounded-lg"><X size={18} /></button>
            </div>
            <form onSubmit={handleAddSource} className="flex flex-col gap-4">
              <div>
                <label className="text-sm font-medium text-slate-700 block mb-1.5">Website</label>
                <select value={selectedWebsite ?? ""} onChange={(e) => setSelectedWebsite(Number(e.target.value))}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500">
                  {websites.map((w) => <option key={w.id} value={w.id}>{w.domain}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700 block mb-1.5">Source name</label>
                <input type="text" value={newSourceName} onChange={(e) => setNewSourceName(e.target.value)}
                  placeholder="e.g. Google Reviews"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              </div>
              <div className="flex gap-3 mt-2">
                <button type="button" onClick={() => setShowAdd(false)}
                  className="flex-1 py-2.5 text-sm font-medium text-slate-700 border border-slate-300 rounded-lg hover:bg-slate-50">Cancel</button>
                <Button type="submit" className="flex-1" disabled={adding || !selectedWebsite}>
                  {adding ? "Adding..." : "Add source"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
            {[
              { label: "Total reviews", value: String(reviews.length) },
              { label: "Avg rating",    value: avgRating },
              { label: "Positive",      value: String(positive) },
              { label: "Negative",      value: String(negative) },
            ].map((k) => (
              <Card key={k.label} className="p-4 text-center">
                <p className="text-2xl font-black text-slate-900">{k.value}</p>
                <p className="text-xs text-slate-500 mt-1">{k.label}</p>
              </Card>
            ))}
          </div>

          {/* Filtres par source */}
          {sources.length > 0 && (
            <div className="flex items-center gap-2 mb-6 flex-wrap">
              <button onClick={() => loadBySource(null)}
                className={"px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors " + (activeSource === null ? "bg-indigo-600 text-white border-indigo-600" : "border-slate-200 text-slate-600 hover:bg-slate-50")}>
                All
              </button>
              {sources.map((s) => (
                <button key={s.id} onClick={() => loadBySource(s.id)}
                  className={"px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors " + (activeSource === s.id ? "bg-indigo-600 text-white border-indigo-600" : "border-slate-200 text-slate-600 hover:bg-slate-50")}>
                  {s.name}
                </button>
              ))}
            </div>
          )}

          {/* Liste des avis */}
          {reviews.length === 0 ? (
            <Card className="p-12 text-center">
              <Star size={40} className="text-slate-200 mx-auto mb-4" />
              <p className="font-semibold text-slate-900 mb-1">No reviews yet</p>
              <p className="text-sm text-slate-500 mb-4">Add a review source to start collecting reviews.</p>
              <Button onClick={() => setShowAdd(true)}><Plus size={16} /> Add source</Button>
            </Card>
          ) : (
            <div className="flex flex-col gap-3">
              {reviews.map((review) => (
                <Card key={review.id} className="p-5">
                  <div className="flex items-start justify-between gap-4 mb-3">
                    <div>
                      <p className="font-semibold text-slate-900">{review.author_name}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <StarRating rating={review.rating} />
                        <span className="text-xs text-slate-400">{timeAgo(review.review_date)}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className={"text-xs px-2 py-0.5 rounded-full border font-medium " + sentimentColor(review.sentiment)}>
                        {review.sentiment}
                      </span>
                      {review.is_approved && (
                        <span className="text-xs px-2 py-0.5 rounded-full border text-emerald-600 bg-emerald-50 border-emerald-200 font-medium">✓ Approved</span>
                      )}
                    </div>
                  </div>
                  {review.text && <p className="text-sm text-slate-600 mb-4 leading-relaxed">{review.text}</p>}
                  {!review.is_approved && (
                    <Button size="sm" onClick={() => handleApprove(review.id)}>
                      <ThumbsUp size={13} /> Approve
                    </Button>
                  )}
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
