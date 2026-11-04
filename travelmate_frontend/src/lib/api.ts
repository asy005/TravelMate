/**
 * TravelMate Frontend API Client
 * Centralized API calls, base URL configuration, authentication headers,
 * and error handling.
 */

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

/**
 * Resolves relative or absolute asset/image URLs against the backend API_BASE_URL.
 * Preserves remote (Unsplash, external) and data: URIs as-is.
 */
export function resolveImageUrl(path?: string | null): string {
  if (!path) return "";
  if (path.startsWith("http://") || path.startsWith("https://") || path.startsWith("data:")) {
    return path;
  }
  const clean = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${clean}`;
}

export function authHeaders(): Record<string, string> {
  const token =
    localStorage.getItem("travelmate_token") ||
    localStorage.getItem("access_token");
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export function extractErrorMessage(data: any, fallback: string): string {
  if (!data) return fallback;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail) && data.detail.length > 0) {
    return data.detail
      .map((item: any) => {
        if (typeof item === "string") return item;
        const loc = item.loc ? item.loc.slice(-1)[0] : "";
        return loc ? `${loc}: ${item.msg || "invalid"}` : (item.msg || JSON.stringify(item));
      })
      .join(", ");
  }
  if (typeof data.message === "string") return data.message;
  return fallback;
}

// ─── Assistant & Conversational Engine ───────────────────────────────────────

export interface AssistantMessageResponse {
  session_id: string;
  reply: string;
  slots: Record<string, any>;
  missing_slots: string[];
  ready_for_plan: boolean;
  plan: Record<string, any> | null;
  recommendations?: any[];
}

export async function sendAssistantMessage(
  sessionId: string | null,
  message: string
): Promise<AssistantMessageResponse> {
  const response = await fetch(`${API_BASE_URL}/assistant/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });

  if (!response.ok) {
    throw new Error("Assistant backend error");
  }

  return response.json();
}

export async function getAssistantSession(sessionId: string) {
  const response = await fetch(
    `${API_BASE_URL}/assistant/session/${sessionId}`
  );

  if (!response.ok) {
    return null;
  }

  return response.json();
}

export async function resetAssistantSession(sessionId: string) {
  const response = await fetch(`${API_BASE_URL}/assistant/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });

  if (!response.ok) {
    throw new Error("Failed to reset assistant session");
  }

  return response.json();
}

export async function chatWithBot(prompt: string): Promise<{ reply?: string; error?: string }> {
  const res = await fetch(`${API_BASE_URL}/chat/bot`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(extractErrorMessage(data, `Chat failed (${res.status})`));
  }
  return res.json();
}

// ─── Destinations ────────────────────────────────────────────────────────────

export interface DestinationsPage {
  items: any[];
  total: number;
}

export async function getDestinationsPage(opts: {
  skip?: number;
  limit?: number;
  q?: string;
  category?: string;
  budget?: string;
  state?: string;
  mood?: string;
  season?: string;
}): Promise<DestinationsPage> {
  const params = new URLSearchParams({
    skip: String(opts.skip ?? 0),
    limit: String(opts.limit ?? 20),
    paginated: "true",
  });
  if (opts.q) params.set("q", opts.q);
  if (opts.category && opts.category !== "All") params.set("category", opts.category);
  if (opts.budget && opts.budget !== "All") params.set("budget", opts.budget);
  if (opts.state && opts.state !== "All") params.set("state", opts.state);
  if (opts.mood && opts.mood !== "All") params.set("mood", opts.mood);
  if (opts.season && opts.season !== "All") params.set("season", opts.season);
  const res = await fetch(`${API_BASE_URL}/destinations/?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to load destinations");
  const data = await res.json();
  if (Array.isArray(data)) return { items: data, total: data.length };
  return data as DestinationsPage;
}

export async function getDestinationsList() {
  const res = await fetch(`${API_BASE_URL}/destinations/?limit=100`);
  if (!res.ok) throw new Error("Failed to load destinations");
  return res.json();
}

export async function getDestinationById(id: string | number) {
  const res = await fetch(`${API_BASE_URL}/destinations/${id}`);
  if (!res.ok) throw new Error("Destination not found");
  return res.json();
}

export async function getDestinationStates(): Promise<string[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/destinations/states`);
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

// ─── ML Recommendations ─────────────────────────────────────────────────────

export interface MLRecommendation {
  destination_id: string;
  destination_name: string;
  state: string;
  city?: string;
  category: string;
  average_budget: number;
  ideal_duration?: number;
  ml_score: number;
  recommendation_score: number;
  image?: string;
  thumbnail_url?: string;
  reason?: string;
}

export interface MLRecommendationsResponse {
  method: string;
  count: number;
  recommendations: MLRecommendation[];
}

export async function getMLRecommendations(opts: {
  age?: number;
  travel_style?: string;
  budget?: "Low" | "Medium" | "High";
  preferred_category?: string;
  preferred_season?: string;
  top_k?: number;
}): Promise<MLRecommendationsResponse> {
  const payload = {
    age: opts.age ?? 30,
    travel_style: opts.travel_style ?? "leisure",
    budget: opts.budget ?? "Medium",
    preferred_category: opts.preferred_category ?? "Beach",
    preferred_season: opts.preferred_season ?? "winter",
    top_k: opts.top_k ?? 3,
  };
  const res = await fetch(`${API_BASE_URL}/recommend/ml`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`ML recommendations failed: ${res.status}`);
  return res.json();
}

export async function analyzeMood(mood: string) {
  const url = `${API_BASE_URL}/recommend?query=${encodeURIComponent(mood)}`;
  const response = await fetch(url, { method: "GET" });
  if (!response.ok) throw new Error("Backend error");
  return response.json();
}

// ─── Hotels & Packages ───────────────────────────────────────────────────────

export async function getHotelDetails(hotelId: string | number) {
  const response = await fetch(`${API_BASE_URL}/hotels/${hotelId}`);
  if (!response.ok) throw new Error("Failed to load hotel details");
  return response.json();
}

export async function getPackageDetails(packageId: string | number) {
  const response = await fetch(`${API_BASE_URL}/packages/${packageId}`);
  if (!response.ok) throw new Error("Failed to load package details");
  return response.json();
}

export async function selectPackage(
  sessionId: string,
  destinationId: number,
  packageId: number
) {
  const response = await fetch(`${API_BASE_URL}/packages/select`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      destination_id: destinationId,
      package_id: packageId,
    }),
  });
  if (!response.ok) throw new Error("Failed to select package");
  return response.json();
}

export async function selectHotel(
  sessionId: string,
  destinationId: number,
  hotelId: number
) {
  const response = await fetch(`${API_BASE_URL}/hotels/select`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      destination_id: destinationId,
      hotel_id: hotelId,
    }),
  });
  if (!response.ok) throw new Error("Failed to select hotel");
  return response.json();
}

// ─── Bookings & Payments ─────────────────────────────────────────────────────

export interface BookingCreatePayload {
  hotel_id: number;
  destination_id?: number;
  session_id?: string;
  guest_name: string;
  guest_email: string;
  guest_phone: string;
  check_in_date: string;
  check_out_date: string;
  num_rooms: number;
  num_guests: number;
  special_requests?: string;
}

export async function createBooking(payload: BookingCreatePayload) {
  const response = await fetch(`${API_BASE_URL}/bookings/`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || "Failed to create booking");
  }

  return response.json();
}

export interface PaymentOrderResponse {
  order_id: string;
  amount: number;
  currency: string;
  key_id: string;
  booking_reference: string;
  is_demo?: boolean;
  simulation_notice?: string | null;
}

export async function createPaymentOrder(bookingReference: string): Promise<PaymentOrderResponse> {
  const response = await fetch(
    `${API_BASE_URL}/bookings/${bookingReference}/create-order`,
    { method: "POST" }
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || "Failed to start payment");
  }
  return response.json();
}

export interface VerifyPaymentPayload {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

export async function verifyPayment(bookingReference: string, payload: VerifyPaymentPayload) {
  const response = await fetch(
    `${API_BASE_URL}/bookings/${bookingReference}/verify-payment`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || "Payment verification failed");
  }
  return response.json();
}

export async function getBooking(bookingReference: string) {
  const response = await fetch(`${API_BASE_URL}/bookings/${bookingReference}`);
  if (!response.ok) throw new Error("Booking not found");
  return response.json();
}

// ─── Favorites ───────────────────────────────────────────────────────────────

export async function getFavorites(): Promise<any[]> {
  const res = await fetch(`${API_BASE_URL}/favorites`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to load favorites");
  return res.json();
}

export async function addFavorite(destinationId: number | string, payload?: any) {
  const res = await fetch(`${API_BASE_URL}/favorites/add?destination_id=${destinationId}`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload || {}),
  });
  if (!res.ok) throw new Error("Failed to add favorite");
  return res.json();
}

export async function removeFavorite(destinationId: number | string) {
  const res = await fetch(`${API_BASE_URL}/favorites/${destinationId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (res.ok) return res.json();

  // Fallback to query param if router used legacy path
  const fallback = await fetch(`${API_BASE_URL}/favorites/remove?destination_id=${destinationId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!fallback.ok) throw new Error("Failed to remove favorite");
  return fallback.json();
}

// ─── Image Landmark & Photo Mood ─────────────────────────────────────────────

export async function predictLandmark(file: File) {
  const token = localStorage.getItem("travelmate_token") || localStorage.getItem("access_token");
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE_URL}/image/landmark`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(extractErrorMessage(data, `Landmark detection failed (${res.status})`));
  }
  return res.json();
}

export async function predictPhotoMood(file: File) {
  const token = localStorage.getItem("travelmate_token") || localStorage.getItem("access_token");
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE_URL}/photo/mood`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(extractErrorMessage(data, `Photo mood prediction failed (${res.status})`));
  }
  return res.json();
}

// ─── Highlights, Nearby & Route Optimization ─────────────────────────────────

export async function getHighlights(query: string, destination?: string) {
  const target = destination || query;
  const res = await fetch(
    `${API_BASE_URL}/highlights/?query=${encodeURIComponent(query)}&destination=${encodeURIComponent(target)}`
  );
  if (!res.ok) throw new Error(`Highlights service error (${res.status})`);
  return res.json();
}

export async function getNearbySpots(lat: number | string, lon: number | string) {
  const res = await fetch(`${API_BASE_URL}/nearby/?lat=${lat}&lon=${lon}`);
  if (!res.ok) throw new Error(`Nearby service error (${res.status})`);
  return res.json();
}

export async function optimizeRoute(payload: {
  points: any[];
  return_to_start?: boolean;
  destination_name?: string;
}) {
  const res = await fetch(`${API_BASE_URL}/routes/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Route optimization failed (${res.status})`);
  return res.json();
}

export async function generatePackingList(payload: {
  destination: string;
  days: number;
  weather?: string;
  activities?: string[];
}) {
  const res = await fetch(`${API_BASE_URL}/packing/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Packing service error (${res.status})`);
  return res.json();
}

export async function generatePlan(destination: string, days: number) {
  const res = await fetch(`${API_BASE_URL}/plan/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ destination, days }),
  });
  if (!res.ok) throw new Error(`Plan generation failed (${res.status})`);
  return res.json();
}

// ─── Authentication Endpoints ────────────────────────────────────────────────

export async function loginUser(payload: any, signal?: AbortSignal) {
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(extractErrorMessage(data, "Invalid email or password"));
  }
  return data;
}

export async function signupUser(payload: any) {
  const res = await fetch(`${API_BASE_URL}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(extractErrorMessage(data, "Signup failed"));
  }
  return data;
}

export async function requestPasswordReset(email: string) {
  return fetch(`${API_BASE_URL}/auth/password-reset/request`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export async function confirmPasswordReset(payload: { token: string; new_password: string }) {
  const res = await fetch(`${API_BASE_URL}/auth/password-reset/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(extractErrorMessage(data, "Password reset failed"));
  }
  return data;
}

export async function logoutUser(refreshToken?: string | null) {
  if (!refreshToken) return;
  return fetch(`${API_BASE_URL}/auth/logout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  }).catch(() => {});
}

export async function refreshAuthToken(refreshToken: string) {
  const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!res.ok) throw new Error("Session expired");
  return res.json();
}

// ─── Partner Portal ──────────────────────────────────────────────────────────

export interface PartnerRegisterPayload {
  business_name: string;
  partner_type: string;
  contact_email?: string;
  contact_phone?: string;
  description?: string;
  address?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  photos?: string[];
}

export async function uploadPartnerPhoto(file: File): Promise<{ url: string; filename: string }> {
  const token = localStorage.getItem("travelmate_token") || localStorage.getItem("access_token");
  if (!token) throw new Error("You must be logged in to upload photos.");
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE_URL}/partners/upload-photo`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(extractErrorMessage(data, "Failed to upload photo"));
  }
  return res.json();
}

export async function registerPartner(payload: PartnerRegisterPayload) {
  const res = await fetch(`${API_BASE_URL}/partners/register`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(extractErrorMessage(data, "Failed to register as a partner"));
  }
  return res.json();
}

export async function getMyPartnerProfile() {
  const res = await fetch(`${API_BASE_URL}/partners/me`, { headers: authHeaders() });
  if (res.status === 401) throw new Error("401");
  if (!res.ok) return null;
  return res.json();
}

export async function getMyListings() {
  const res = await fetch(`${API_BASE_URL}/partners/listings`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to load listings");
  return res.json();
}

export interface ListingPayload {
  destination_id: number;
  name: string;
  category?: string;
  price_tier?: string;
  price?: number;
  rating?: number;
  amenities?: string[];
  description?: string;
  thumbnail_url?: string;
  photos?: string[];
  extra?: { duration_days?: number; capacity?: number };
}

export async function createListing(listingType: "hotel" | "package", payload: ListingPayload) {
  const res = await fetch(`${API_BASE_URL}/partners/listings/${listingType}`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Failed to create listing");
  }
  return res.json();
}

export async function updateListing(
  listingType: "hotel" | "package",
  listingId: number,
  payload: Partial<ListingPayload>
) {
  const res = await fetch(`${API_BASE_URL}/partners/listings/${listingType}/${listingId}`, {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to update listing");
  return res.json();
}

export async function getPartnerBookings() {
  const res = await fetch(`${API_BASE_URL}/partners/bookings`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to load bookings");
  return res.json();
}

export async function updateBookingStatus(bookingReference: string, status: string) {
  const res = await fetch(`${API_BASE_URL}/partners/bookings/${bookingReference}/status`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error("Failed to update booking status");
  return res.json();
}

export async function getPartnerAnalytics() {
  const res = await fetch(`${API_BASE_URL}/partners/analytics`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to load analytics");
  return res.json();
}

// ─── Reviews API ─────────────────────────────────────────────────────────────

export interface ReviewSubmitPayload {
  hotel_id?: number;
  package_id?: number;
  rating: number;
  review_text: string;
}

export interface ReviewOut {
  id: number;
  csv_review_id: string | null;
  csv_user_id: string | null;
  user_id: number | null;
  hotel_id: number | null;
  package_id: number | null;
  rating: number;
  review_text: string;
  review_date: string | null;
  images: string | null;
  sentiment_label: string | null;
  sentiment_score: number | null;
  created_at: string | null;
}

export interface ReviewSummaryOut {
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

export async function submitReview(payload: ReviewSubmitPayload): Promise<ReviewOut> {
  const token = localStorage.getItem("travelmate_token") || localStorage.getItem("access_token");
  const res = await fetch(`${API_BASE_URL}/reviews/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? "Failed to submit review");
  }
  return res.json();
}

export async function getHotelReviews(hotelId: number): Promise<ReviewSummaryOut> {
  const res = await fetch(`${API_BASE_URL}/reviews/hotel/${hotelId}`);
  if (!res.ok) throw new Error("Failed to fetch hotel reviews");
  return res.json();
}

export async function getPackageReviews(packageId: number): Promise<ReviewSummaryOut> {
  const res = await fetch(`${API_BASE_URL}/reviews/package/${packageId}`);
  if (!res.ok) throw new Error("Failed to fetch package reviews");
  return res.json();
}

export async function getMyReviews(): Promise<ReviewOut[]> {
  const token = localStorage.getItem("travelmate_token") || localStorage.getItem("access_token");
  const res = await fetch(`${API_BASE_URL}/reviews/me`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("Failed to fetch your reviews");
  return res.json();
}

// ─── OCR & Translation ───────────────────────────────────────────────────────

export interface OCRResult {
  text: string | null;
  engine: string | null;
  filename: string;
  file_size_kb: number;
  error: string | null;
}

export interface TranslateResult {
  translated_text: string | null;
  source_language: string | null;
  target_language: string;
  provider: string | null;
  error: string | null;
}

export interface OCRTranslateResult {
  original_text: string | null;
  translated_text: string | null;
  source_language: string | null;
  target_language: string;
  ocr_engine: string | null;
  translation_provider: string | null;
  filename: string;
  error: string | null;
}

export interface LanguageOption {
  code: string;
  name: string;
}

export async function extractOCRText(file: File, lang = "eng"): Promise<OCRResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE_URL}/ocr/extract?lang=${encodeURIComponent(lang)}`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`OCR request failed: ${res.status}`);
  return res.json();
}

export async function translateText(
  text: string,
  targetLang: string,
  sourceLang = "auto"
): Promise<TranslateResult> {
  const res = await fetch(`${API_BASE_URL}/translate/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, target_lang: targetLang, source_lang: sourceLang }),
  });
  if (!res.ok) throw new Error(`Translation request failed: ${res.status}`);
  return res.json();
}

export interface BatchTranslateItem {
  original_text: string;
  translated_text?: string | null;
  provider?: string | null;
  error?: string | null;
}

export interface BatchTranslateResponse {
  items: BatchTranslateItem[];
  target_language: string;
}

export async function translateTextsBatch(
  texts: string[],
  targetLang: string,
  sourceLang = "auto"
): Promise<BatchTranslateResponse> {
  const res = await fetch(`${API_BASE_URL}/translate/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texts, target_lang: targetLang, source_lang: sourceLang }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail || `Batch translation failed (${res.status})`);
  }
  return res.json();
}

export async function ocrAndTranslate(
  file: File,
  targetLang: string,
  ocrLang = "eng"
): Promise<OCRTranslateResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(
    `${API_BASE_URL}/translate/ocr?target_lang=${encodeURIComponent(targetLang)}&ocr_lang=${encodeURIComponent(ocrLang)}`,
    {
      method: "POST",
      body: form,
    }
  );
  if (!res.ok) throw new Error(`OCR+Translate request failed: ${res.status}`);
  return res.json();
}

export async function getSupportedLanguages(): Promise<LanguageOption[]> {
  const res = await fetch(`${API_BASE_URL}/translate/languages`);
  if (!res.ok) throw new Error(`Languages request failed: ${res.status}`);
  return res.json();
}

// ─── Multi-Currency Conversion ───────────────────────────────────────────────

export interface SupportedCurrency {
  code: string;
  name: string;
  symbol: string;
}

export interface CurrencyRatesResponse {
  base: string;
  rates: Record<string, number>;
  timestamp: string;
  source: string;
  is_stale: boolean;
  stale_warning: string | null;
  supported_currencies: SupportedCurrency[];
}

export interface ConvertedAmountResponse {
  original_amount: number;
  original_currency: string;
  converted_amount: number;
  target_currency: string;
  symbol: string;
  rate: number;
  rate_timestamp: string;
  source: string;
  is_stale: boolean;
  stale_warning: string | null;
  disclaimer: string;
  price_guarantee: boolean;
}

export interface ConvertedBudgetResponse {
  currency: string;
  currency_symbol: string;
  base_currency?: string;
  exchange_rate?: number;
  rate_timestamp?: string;
  rate_source?: string;
  is_stale_rate?: boolean;
  stale_warning?: string | null;
  total_budget: number;
  estimated_total: number;
  remaining_budget: number;
  cost_per_traveler: number;
  cost_per_day: number;
  breakdown: Record<string, number>;
  original_inr?: {
    total_budget: number;
    estimated_total: number;
    remaining_budget: number;
    cost_per_traveler: number;
    cost_per_day: number;
    breakdown: Record<string, number>;
  };
  converted_breakdown?: Record<string, number>;
  converted_total_budget?: number;
  converted_estimated_total?: number;
  converted_remaining_budget?: number;
  converted_cost_per_traveler?: number;
  converted_cost_per_day?: number;
  status: string;
  tier?: string;
  budget_source?: string;
  hotel_used?: any;
  package_used?: any;
  alternative_hotels?: any[];
  optimization_method?: string;
  disclaimer?: string;
  price_guarantee?: boolean;
}

export async function getSupportedCurrencies(): Promise<SupportedCurrency[]> {
  const res = await fetch(`${API_BASE_URL}/currency/supported`);
  if (!res.ok) throw new Error(`Supported currencies request failed: ${res.status}`);
  return res.json();
}

export async function getCurrencyRates(base = "INR", forceRefresh = false): Promise<CurrencyRatesResponse> {
  const res = await fetch(
    `${API_BASE_URL}/currency/rates?base=${encodeURIComponent(base)}&force_refresh=${forceRefresh}`
  );
  if (!res.ok) throw new Error(`Currency rates request failed: ${res.status}`);
  return res.json();
}

export async function convertSingleAmount(amount: number, targetCurrency: string): Promise<ConvertedAmountResponse> {
  const res = await fetch(`${API_BASE_URL}/currency/convert`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ amount, target_currency: targetCurrency }),
  });
  if (!res.ok) throw new Error(`Currency conversion request failed: ${res.status}`);
  return res.json();
}

export async function convertBudgetData(budget: any, targetCurrency: string): Promise<ConvertedBudgetResponse> {
  const res = await fetch(`${API_BASE_URL}/currency/convert-budget`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ budget, target_currency: targetCurrency }),
  });
  if (!res.ok) throw new Error(`Budget conversion request failed: ${res.status}`);
  return res.json();
}
