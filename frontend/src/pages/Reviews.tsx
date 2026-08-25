import React, { useState } from "react";
import { Card, Button } from "../components/ui";
import { Star, RefreshCw } from "lucide-react";

const reviews = [
  { author: "Thomas M.", rating: 5, text: "Excellent service! The team was incredibly helpful and professional. I will definitely come back.", date: "2 days ago", platform: "Google", needsResponse: false },
  { author: "Franziska L.", rating: 5, text: "Very friendly staff and great atmosphere. Highly recommend to anyone looking for quality service.", date: "4 days ago", platform: "Google", needsResponse: false },
  { author: "Karl B.", rating: 2, text: "Waited too long before being served. The result was okay but the service experience was disappointing.", date: "1 week ago", platform: "Google", needsResponse: true },
  { author: "Sophie A.", rating: 4, text: "Good overall experience. Would be better with a bit more attention to detail.", date: "2 weeks ago", platform: "Google", needsResponse: false },
  { author: "Henri D.", rating: 5, text: "Amazing! Exactly what I was looking for. The quality is outstanding.", date: "3 weeks ago", platform: "Yelp", needsResponse: false },
];

function Stars({ rating }: { rating: number }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: 5 }, (_, i) => (
        <Star
          key={i}
          size={14}
          className={i < rating ? "text-amber-400 fill-amber-400" : "text-slate-200 fill-slate-200"}
        />
      ))}
    </div>
  );
}

function AIModal({ review, onClose }: { review: typeof reviews[0], onClose: () => void }) {
  const [regenerating, setRegen] = useState(false);
  const suggestion = `Thank you for your feedback, ${review.author.split(" ")[0]}. We're sorry to hear that your experience didn't meet your expectations. We take all feedback seriously and would love the opportunity to make things right. Please feel free to reach out to us directly so we can address your concerns.`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl border border-slate-200">
        <div className="p-5 border-b border-slate-100">
          <div className="flex items-center justify-between">
            <h2 className="font-bold text-slate-900">AI Response Assistant</h2>
            <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl leading-none">×</button>
          </div>
        </div>
        <div className="p-5">
          {/* Original review */}
          <div className="p-4 bg-slate-50 rounded-xl mb-4">
            <div className="flex items-center gap-2 mb-2">
              <Stars rating={review.rating} />
              <span className="text-xs text-slate-500">by {review.author}</span>
            </div>
            <p className="text-sm text-slate-700">"{review.text}"</p>
          </div>

          {/* AI suggestion */}
          <div className="p-4 bg-indigo-50 border border-indigo-100 rounded-xl mb-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold text-indigo-600 bg-indigo-100 px-2 py-0.5 rounded-full">AI-generated suggestion</span>
            </div>
            <p className="text-sm text-slate-700">{suggestion}</p>
          </div>

          <p className="text-xs text-slate-400 mb-4">
            ⚠️ This response is AI-generated. Review and edit before publishing. You must approve it before it is sent.
          </p>

          <div className="flex gap-2 flex-wrap">
            <Button
              size="sm"
              variant="outline"
              onClick={() => { setRegen(true); setTimeout(() => setRegen(false), 1500); }}
            >
              <RefreshCw size={12} className={regenerating ? "animate-spin" : ""} />
              Regenerate
            </Button>
            <Button size="sm" variant="outline">Edit</Button>
            <Button size="sm" variant="outline" onClick={() => { navigator.clipboard.writeText(suggestion); onClose(); }}>
              Copy response
            </Button>
            <Button size="sm" className="ml-auto" onClick={onClose}>Done</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Reviews() {
  const [aiReview, setAiReview] = useState<typeof reviews[0] | null>(null);

  const avg = (reviews.reduce((s, r) => s + r.rating, 0) / reviews.length).toFixed(1);

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto">
      {aiReview && <AIModal review={aiReview} onClose={() => setAiReview(null)} />}

      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Online Reviews</h1>
        <p className="text-slate-500 mt-1">Monitor your customer reputation across platforms.</p>
      </div>

      {/* Summary */}
      <div className="grid sm:grid-cols-3 gap-4 mb-8">
        <Card className="p-5 text-center">
          <p className="text-xs text-slate-500 mb-2">Average rating</p>
          <div className="text-4xl font-black text-slate-900 mb-1">{avg} ★</div>
          <div className="flex justify-center">
            <Stars rating={Math.round(Number(avg))} />
          </div>
        </Card>
        <Card className="p-5 text-center">
          <p className="text-xs text-slate-500 mb-2">Total reviews</p>
          <div className="text-4xl font-black text-slate-900 mb-1">248</div>
          <p className="text-xs text-slate-400">All platforms</p>
        </Card>
        <Card className="p-5 text-center">
          <p className="text-xs text-slate-500 mb-2">New this month</p>
          <div className="text-4xl font-black text-slate-900 mb-1">18</div>
          <p className="text-xs text-emerald-600">↑ +3 vs last month</p>
        </Card>
      </div>

      {/* Reviews list */}
      <div className="flex flex-col gap-4">
        {reviews.map((review, i) => (
          <Card key={i} className={`p-5 ${review.needsResponse ? "border-amber-200 bg-amber-50/30" : ""}`}>
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div className="flex-1">
                <div className="flex items-center gap-3 flex-wrap mb-2">
                  <Stars rating={review.rating} />
                  <span className="text-sm font-semibold text-slate-900">{review.author}</span>
                  <span className="text-xs text-slate-400">{review.platform} · {review.date}</span>
                  {review.needsResponse && (
                    <span className="px-2 py-0.5 bg-amber-100 text-amber-700 text-xs font-medium rounded-full border border-amber-200">
                      ⚠️ Needs response
                    </span>
                  )}
                </div>
                <p className="text-sm text-slate-700 leading-relaxed">"{review.text}"</p>
              </div>
            </div>
            {review.needsResponse && (
              <div className="mt-4 pt-4 border-t border-amber-200">
                <Button size="sm" onClick={() => setAiReview(review)}>
                  ✨ Generate response
                </Button>
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
