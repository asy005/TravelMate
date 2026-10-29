/**
 * ReviewsSection.tsx
 * ------------------
 * Displays aggregated review sentiment and the most recent reviews for a
 * hotel or package on the DestinationPage (Phase 3).
 *
 * Props
 * -----
 *   entityType  "hotel" | "package"
 *   entityId    The DB id of the hotel or package.
 *
 * Data is fetched from GET /reviews/{entityType}/{entityId}.
 * No fabricated ratings are shown — all data comes from the API.
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { Star, ThumbsUp, ThumbsDown, Minus } from "lucide-react";

const API_BASE = "http://127.0.0.1:8000";

interface ReviewOut {
  id: number;
  rating: number;
  review_text: string;
  sentiment_label: string | null;
  sentiment_score: number | null;
  csv_user_id: string | null;
  user_id: number | null;
  created_at: string | null;
  review_date: string | null;
}

interface ReviewSummaryOut {
  entity_type: string;
  entity_id: number;
  total_reviews: number;
  average_rating: number | null;
  positive_count: number;
  neutral_count: number;
  negative_count: number;
  positive_pct: number;
  negative_pct: number;
  recent_reviews: ReviewOut[];
}

interface Props {
  entityType: "hotel" | "package";
  entityId: number;
}

function SentimentBadge({ label }: { label: string | null }) {
  if (!label) return null;
  const map: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
    positive: {
      color: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
      icon: <ThumbsUp className="w-3 h-3 inline mr-1" />,
      text: "Positive",
    },
    neutral: {
      color: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
      icon: <Minus className="w-3 h-3 inline mr-1" />,
      text: "Neutral",
    },
    negative: {
      color: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
      icon: <ThumbsDown className="w-3 h-3 inline mr-1" />,
      text: "Negative",
    },
  };
  const style = map[label] ?? map["neutral"];
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${style.color}`}>
      {style.icon}
      {style.text}
    </span>
  );
}

function StarRating({ rating }: { rating: number }) {
  return (
    <span className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <Star
          key={i}
          className={`w-4 h-4 ${
            i <= Math.round(rating)
              ? "fill-yellow-400 text-yellow-400"
              : "text-gray-300 dark:text-gray-600"
          }`}
        />
      ))}
      <span className="ml-1 text-sm font-medium">{rating.toFixed(1)}</span>
    </span>
  );
}

export function ReviewsSection({ entityType, entityId }: Props) {
  const [summary, setSummary] = useState<ReviewSummaryOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!entityId) return;
    setLoading(true);
    setError(null);

    axios
      .get<ReviewSummaryOut>(`${API_BASE}/reviews/${entityType}/${entityId}`)
      .then((res) => {
        setSummary(res.data);
      })
      .catch((err) => {
        if (err.response?.status === 404) {
          setError("No reviews found.");
        } else {
          setError("Could not load reviews.");
        }
      })
      .finally(() => setLoading(false));
  }, [entityType, entityId]);

  if (loading) {
    return (
      <div className="animate-pulse rounded-2xl bg-card/70 p-6 border border-white/10 h-32" />
    );
  }

  if (error || !summary) {
    return (
      <div className="rounded-2xl bg-card/70 p-6 border border-white/10 text-muted-foreground text-sm">
        {error ?? "No reviews available."}
      </div>
    );
  }

  const { total_reviews, average_rating, positive_pct, negative_pct, recent_reviews } = summary;

  return (
    <div className="bg-card/70 backdrop-blur-xl shadow-xl p-6 rounded-2xl border border-white/10 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-2xl font-semibold">Guest Reviews</h2>
        {total_reviews > 0 && (
          <span className="text-sm text-muted-foreground">{total_reviews} review{total_reviews !== 1 ? "s" : ""}</span>
        )}
      </div>

      {total_reviews === 0 ? (
        <p className="text-muted-foreground text-sm">No reviews yet. Be the first to review!</p>
      ) : (
        <>
          {/* Summary strip */}
          <div className="flex flex-wrap gap-6 items-center">
            {average_rating !== null && (
              <div>
                <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Avg Rating</p>
                <StarRating rating={average_rating} />
              </div>
            )}
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wide mb-1">Sentiment</p>
              <div className="flex gap-2 flex-wrap">
                <span className="text-xs text-green-600 dark:text-green-400 font-medium">
                  👍 {positive_pct}% positive
                </span>
                <span className="text-xs text-red-500 dark:text-red-400 font-medium">
                  👎 {negative_pct}% negative
                </span>
              </div>
            </div>
          </div>

          {/* Sentiment bar */}
          <div className="h-2 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden flex">
            <div
              className="bg-green-500 transition-all"
              style={{ width: `${positive_pct}%` }}
            />
            <div
              className="bg-yellow-400 transition-all"
              style={{ width: `${100 - positive_pct - negative_pct}%` }}
            />
            <div
              className="bg-red-500 transition-all"
              style={{ width: `${negative_pct}%` }}
            />
          </div>

          {/* Recent reviews */}
          {recent_reviews.length > 0 && (
            <div className="space-y-4">
              <h3 className="text-lg font-medium">Recent Reviews</h3>
              {recent_reviews.map((rev) => (
                <div
                  key={rev.id}
                  className="p-4 rounded-xl bg-background/60 border border-white/10 space-y-2"
                >
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-3">
                      <StarRating rating={rev.rating} />
                      <SentimentBadge label={rev.sentiment_label} />
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {rev.review_date
                        ? new Date(rev.review_date).toLocaleDateString()
                        : rev.created_at
                        ? new Date(rev.created_at).toLocaleDateString()
                        : ""}
                    </span>
                  </div>
                  <p className="text-sm leading-relaxed">{rev.review_text}</p>
                  <p className="text-xs text-muted-foreground">
                    — {rev.user_id ? `User #${rev.user_id}` : rev.csv_user_id ?? "Guest"}
                  </p>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default ReviewsSection;
