/**
 * ReviewsSection.tsx
 * ------------------
 * Displays aggregated review sentiment, commonly praised aspects, recurring
 * complaints, and verified reviews for a hotel, package, or destination (Phase 3).
 *
 * Props
 * -----
 *   entityType  "hotel" | "package" | "destination"
 *   entityId    The DB id of the hotel, package, or destination.
 *
 * Data is fetched from GET /reviews/{entityType}/{entityId}.
 * No fabricated ratings or sentiment data are shown — all data comes from the API.
 */
import { useEffect, useState } from "react";
import axios from "axios";
import {
  Star,
  ThumbsUp,
  ThumbsDown,
  Minus,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  MessageSquare,
  ShieldCheck,
} from "lucide-react";
import { API_BASE_URL } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const API_BASE = API_BASE_URL;

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
  entity_id: number | string;
  total_reviews: number;
  average_rating: number | null;
  positive_count: number;
  neutral_count: number;
  negative_count: number;
  positive_pct: number;
  negative_pct: number;
  sentiment_summary?: string | null;
  praised_aspects?: string[];
  recurring_complaints?: string[];
  recent_reviews: ReviewOut[];
}

interface Props {
  entityType: "hotel" | "package" | "destination";
  entityId: number;
  title?: string;
}

function SentimentBadge({ label }: { label: string | null }) {
  if (!label) return null;
  const map: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
    positive: {
      color: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800",
      icon: <ThumbsUp className="w-3 h-3 inline mr-1" />,
      text: "Positive",
    },
    neutral: {
      color: "bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300 border-amber-200 dark:border-amber-800",
      icon: <Minus className="w-3 h-3 inline mr-1" />,
      text: "Neutral",
    },
    negative: {
      color: "bg-rose-100 text-rose-800 dark:bg-rose-950/40 dark:text-rose-300 border-rose-200 dark:border-rose-800",
      icon: <ThumbsDown className="w-3 h-3 inline mr-1" />,
      text: "Critical",
    },
  };
  const style = map[label] ?? map["neutral"];
  return (
    <span
      className={`text-xs font-medium px-2 py-0.5 rounded-full border inline-flex items-center ${style.color}`}
    >
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
              ? "fill-amber-400 text-amber-400"
              : "text-muted-foreground/30"
          }`}
        />
      ))}
      <span className="ml-1 text-sm font-semibold">{rating.toFixed(1)}</span>
    </span>
  );
}

export function ReviewsSection({ entityType, entityId, title }: Props) {
  const [summary, setSummary] = useState<ReviewSummaryOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterSentiment, setFilterSentiment] = useState<"all" | "positive" | "negative">("all");

  const fetchReviews = () => {
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
          setError("No review records found.");
        } else {
          setError("Could not load reviews at this moment.");
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchReviews();
  }, [entityType, entityId]);

  const defaultTitle =
    entityType === "destination"
      ? "Guest Reviews & Sentiment Insights"
      : entityType === "hotel"
      ? "Guest Reviews & Hotel Feedback"
      : "Traveler Reviews & Package Experience";

  const sectionTitle = title || defaultTitle;

  if (loading) {
    return (
      <div className="bg-card/70 backdrop-blur-xl shadow-sm p-6 rounded-2xl border border-border/60 space-y-4 animate-pulse">
        <div className="h-6 w-52 bg-muted rounded-md" />
        <div className="h-4 w-72 bg-muted/60 rounded-md" />
        <div className="h-20 bg-muted/30 rounded-xl" />
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="h-24 bg-muted/30 rounded-xl" />
          <div className="h-24 bg-muted/30 rounded-xl" />
        </div>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="bg-card/70 backdrop-blur-xl shadow-sm p-6 rounded-2xl border border-border/60 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-foreground">{sectionTitle}</h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchReviews}
            className="text-xs h-7 px-2"
          >
            <RefreshCw className="h-3 w-3 mr-1" /> Retry
          </Button>
        </div>
        <p className="text-sm text-muted-foreground">{error ?? "Reviews are currently unavailable."}</p>
      </div>
    );
  }

  const {
    total_reviews,
    average_rating,
    positive_pct,
    negative_pct,
    sentiment_summary,
    praised_aspects = [],
    recurring_complaints = [],
    recent_reviews,
  } = summary;

  const neutral_pct = Math.max(0, Math.round(100 - positive_pct - negative_pct));

  const filteredReviews = recent_reviews.filter((rev) => {
    if (filterSentiment === "all") return true;
    if (filterSentiment === "positive") return rev.sentiment_label === "positive";
    if (filterSentiment === "negative") return rev.sentiment_label === "negative";
    return true;
  });

  return (
    <div className="bg-card/80 backdrop-blur-xl shadow-sm p-6 rounded-2xl border border-border/60 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-foreground flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-primary" />
            <span>{sectionTitle}</span>
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Guest feedback analyzed with automated sentiment classification
          </p>
        </div>
        {total_reviews > 0 && (
          <Badge variant="secondary" className="text-xs font-semibold px-2.5 py-1">
            {total_reviews} review{total_reviews !== 1 ? "s" : ""}
          </Badge>
        )}
      </div>

      {total_reviews === 0 ? (
        <div className="p-6 rounded-xl border border-dashed border-border/70 bg-muted/20 text-center space-y-3">
          <ShieldCheck className="h-8 w-8 text-muted-foreground mx-auto" />
          <div className="space-y-1">
            <h4 className="font-semibold text-sm text-foreground">
              No Written Guest Reviews Yet
            </h4>
            <p className="text-xs text-muted-foreground max-w-md mx-auto">
              {average_rating !== null
                ? `Current baseline rating stands at ${average_rating.toFixed(1)} / 5.0 based on curated travel database records. Written reviews will appear as travelers submit their experiences.`
                : "Be the first traveler to leave a detailed review and rating for this place."}
            </p>
          </div>
          {average_rating !== null && (
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-background border border-border/60 text-xs font-medium">
              <StarRating rating={average_rating} />
              <span className="text-muted-foreground">overall rating</span>
            </div>
          )}
        </div>
      ) : (
        <>
          {/* Sentiment Summary Card */}
          {sentiment_summary && (
            <div className="p-4 rounded-xl bg-gradient-to-r from-primary/10 via-primary/5 to-transparent border border-primary/20 flex items-start gap-3">
              <Sparkles className="h-5 w-5 text-primary shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <p className="text-xs font-bold uppercase tracking-wider text-primary">
                  Sentiment Summary
                </p>
                <p className="text-sm font-medium text-foreground">{sentiment_summary}</p>
              </div>
            </div>
          )}

          {/* Aggregate Rating & Sentiment Distribution */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 rounded-xl bg-muted/20 border border-border/40">
            {/* Rating */}
            {average_rating !== null && (
              <div className="space-y-1">
                <span className="text-xs text-muted-foreground uppercase font-semibold">
                  Average Rating
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-3xl font-extrabold text-foreground">
                    {average_rating.toFixed(1)}
                  </span>
                  <div className="space-y-0.5">
                    <StarRating rating={average_rating} />
                    <span className="text-[11px] text-muted-foreground block">
                      Out of 5.0 stars
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Sentiment Breakdown */}
            <div className="md:col-span-2 space-y-2">
              <div className="flex items-center justify-between text-xs font-medium">
                <span className="text-muted-foreground uppercase font-semibold">
                  Sentiment Breakdown
                </span>
                <div className="flex items-center gap-3 text-xs">
                  <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                    👍 {positive_pct}% Pos
                  </span>
                  <span className="text-amber-600 dark:text-amber-400 font-semibold">
                    ➖ {neutral_pct}% Neu
                  </span>
                  <span className="text-rose-600 dark:text-rose-400 font-semibold">
                    👎 {negative_pct}% Neg
                  </span>
                </div>
              </div>

              {/* Tri-color sentiment bar */}
              <div className="h-2.5 rounded-full bg-muted overflow-hidden flex shadow-inner">
                <div
                  className="bg-emerald-500 transition-all duration-500"
                  style={{ width: `${positive_pct}%` }}
                  title={`Positive: ${positive_pct}%`}
                />
                <div
                  className="bg-amber-400 transition-all duration-500"
                  style={{ width: `${neutral_pct}%` }}
                  title={`Neutral: ${neutral_pct}%`}
                />
                <div
                  className="bg-rose-500 transition-all duration-500"
                  style={{ width: `${negative_pct}%` }}
                  title={`Negative: ${negative_pct}%`}
                />
              </div>
            </div>
          </div>

          {/* Praised Aspects & Recurring Complaints */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Praised Aspects */}
            <div className="p-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 space-y-2.5">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-300">
                  Commonly Praised Aspects
                </h4>
              </div>
              {praised_aspects.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {praised_aspects.map((aspect, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center text-xs px-2.5 py-1 rounded-lg bg-emerald-100 text-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-200 border border-emerald-200/60 dark:border-emerald-800/60 font-medium"
                    >
                      <ThumbsUp className="h-3 w-3 mr-1 text-emerald-600 dark:text-emerald-400" />
                      {aspect}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground italic">
                  No recurring praise themes detected in available reviews.
                </p>
              )}
            </div>

            {/* Recurring Complaints */}
            <div className="p-4 rounded-xl border border-rose-500/20 bg-rose-500/5 space-y-2.5">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-rose-600 dark:text-rose-400" />
                <h4 className="text-xs font-bold uppercase tracking-wider text-rose-700 dark:text-rose-300">
                  Recurring Complaints &amp; Issues
                </h4>
              </div>
              {recurring_complaints.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {recurring_complaints.map((issue, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center text-xs px-2.5 py-1 rounded-lg bg-rose-100 text-rose-900 dark:bg-rose-950/60 dark:text-rose-200 border border-rose-200/60 dark:border-rose-800/60 font-medium"
                    >
                      <ThumbsDown className="h-3 w-3 mr-1 text-rose-600 dark:text-rose-400" />
                      {issue}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground italic">
                  No recurring complaints identified in available reviews.
                </p>
              )}
            </div>
          </div>

          {/* Reviews List with Filter */}
          {recent_reviews.length > 0 && (
            <div className="space-y-4 pt-2">
              <div className="flex items-center justify-between flex-wrap gap-2 border-b border-border/50 pb-2">
                <h3 className="text-base font-bold text-foreground">
                  Recent Guest Reviews ({recent_reviews.length})
                </h3>

                <div className="flex items-center gap-1">
                  <Button
                    variant={filterSentiment === "all" ? "secondary" : "ghost"}
                    size="sm"
                    onClick={() => setFilterSentiment("all")}
                    className="text-xs h-7 px-2.5"
                  >
                    All ({recent_reviews.length})
                  </Button>
                  <Button
                    variant={filterSentiment === "positive" ? "secondary" : "ghost"}
                    size="sm"
                    onClick={() => setFilterSentiment("positive")}
                    className="text-xs h-7 px-2.5 text-emerald-600 dark:text-emerald-400"
                  >
                    Positive ({summary.positive_count})
                  </Button>
                  {summary.negative_count > 0 && (
                    <Button
                      variant={filterSentiment === "negative" ? "secondary" : "ghost"}
                      size="sm"
                      onClick={() => setFilterSentiment("negative")}
                      className="text-xs h-7 px-2.5 text-rose-600 dark:text-rose-400"
                    >
                      Critical ({summary.negative_count})
                    </Button>
                  )}
                </div>
              </div>

              <div className="space-y-3">
                {filteredReviews.length === 0 ? (
                  <p className="text-xs text-muted-foreground py-3 text-center">
                    No reviews in this sentiment category.
                  </p>
                ) : (
                  filteredReviews.map((rev) => (
                    <div
                      key={rev.id}
                      className="p-4 rounded-xl bg-background/70 border border-border/60 hover:border-border transition-colors space-y-2 shadow-xs"
                    >
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <div className="flex items-center gap-2.5">
                          <StarRating rating={rev.rating} />
                          <SentimentBadge label={rev.sentiment_label} />
                        </div>
                        <span className="text-[11px] text-muted-foreground">
                          {rev.review_date
                            ? new Date(rev.review_date).toLocaleDateString(undefined, {
                                year: "numeric",
                                month: "short",
                                day: "numeric",
                              })
                            : rev.created_at
                            ? new Date(rev.created_at).toLocaleDateString(undefined, {
                                year: "numeric",
                                month: "short",
                                day: "numeric",
                              })
                            : ""}
                        </span>
                      </div>
                      <p className="text-sm leading-relaxed text-foreground/90 font-normal">
                        "{rev.review_text}"
                      </p>
                      <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1">
                        <span>
                          {rev.user_id ? `Traveler #${rev.user_id}` : rev.csv_user_id || "Guest"}
                        </span>
                        {rev.sentiment_score !== null && (
                          <span className="text-[10px] text-muted-foreground/70">
                            Score: {Number(rev.sentiment_score).toFixed(2)}
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default ReviewsSection;
