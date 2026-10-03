export async function analyzeMood(mood: string) {
  const url = `http://127.0.0.1:8000/recommend?query=${encodeURIComponent(mood)}`;

  const response = await fetch(url, {
    method: "GET",
  });

  if (!response.ok) {
    throw new Error("Backend error");
  }

  return response.json();
}

export interface AssistantMessageResponse {
  session_id: string;
  reply: string;
  slots: Record<string, any>;
  missing_slots: string[];
  ready_for_plan: boolean;
  plan: Record<string, any> | null;
}

export async function sendAssistantMessage(
  sessionId: string | null,
  message: string
): Promise<AssistantMessageResponse> {
  const response = await fetch("http://127.0.0.1:8000/assistant/message", {
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
    `http://127.0.0.1:8000/assistant/session/${sessionId}`
  );

  if (!response.ok) {
    return null;
  }

  return response.json();
}

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
  const token = localStorage.getItem("travelmate_token");
  const response = await fetch("http://127.0.0.1:8000/bookings/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || "Failed to create booking");
  }

  return response.json();
}

export async function createPaymentOrder(bookingReference: string) {
  const response = await fetch(
    `http://127.0.0.1:8000/bookings/${bookingReference}/create-order`,
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
    `http://127.0.0.1:8000/bookings/${bookingReference}/verify-payment`,
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
  const response = await fetch(`http://127.0.0.1:8000/bookings/${bookingReference}`);
  if (!response.ok) {
    throw new Error("Booking not found");
  }
  return response.json();
}
export async function getHotelDetails(hotelId: string | number) {
  const response = await fetch(`http://127.0.0.1:8000/hotels/${hotelId}`);
  if (!response.ok) {
    throw new Error("Failed to load hotel details");
  }
  return response.json();
}

export async function getPackageDetails(packageId: string | number) {
  const response = await fetch(`http://127.0.0.1:8000/packages/${packageId}`);
  if (!response.ok) {
    throw new Error("Failed to load package details");
  }
  return response.json();
}

export async function selectPackage(
  sessionId: string,
  destinationId: number,
  packageId: number
) {
  const response = await fetch("http://127.0.0.1:8000/packages/select", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      destination_id: destinationId,
      package_id: packageId,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to select package");
  }

  return response.json();
}

export async function selectHotel(
  sessionId: string,
  destinationId: number,
  hotelId: number
) {
  const response = await fetch("http://127.0.0.1:8000/hotels/select", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      destination_id: destinationId,
      hotel_id: hotelId,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to select hotel");
  }

  return response.json();
}
// -------- Partner Portal --------
export async function getDestinationsList() {
  const res = await fetch("http://127.0.0.1:8000/destinations/?limit=100");
  if (!res.ok) throw new Error("Failed to load destinations");
  return res.json();
}

function authHeaders() {
  const token = localStorage.getItem("travelmate_token");
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export interface PartnerRegisterPayload {
  business_name: string;
  partner_type: string;
  contact_email?: string;
  contact_phone?: string;
  description?: string;
}

export async function registerPartner(payload: PartnerRegisterPayload) {
  const res = await fetch("http://127.0.0.1:8000/partners/register", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Failed to register as a partner");
  }
  return res.json();
}

export async function getMyPartnerProfile() {
  const res = await fetch("http://127.0.0.1:8000/partners/me", { headers: authHeaders() });
  if (!res.ok) return null;
  return res.json();
}

export async function getMyListings() {
  const res = await fetch("http://127.0.0.1:8000/partners/listings", { headers: authHeaders() });
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
  const res = await fetch(`http://127.0.0.1:8000/partners/listings/${listingType}`, {
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
  const res = await fetch(`http://127.0.0.1:8000/partners/listings/${listingType}/${listingId}`, {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to update listing");
  return res.json();
}

export async function getPartnerBookings() {
  const res = await fetch("http://127.0.0.1:8000/partners/bookings", { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to load bookings");
  return res.json();
}

export async function updateBookingStatus(bookingReference: string, status: string) {
  const res = await fetch(`http://127.0.0.1:8000/partners/bookings/${bookingReference}/status`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error("Failed to update booking status");
  return res.json();
}

export async function getPartnerAnalytics() {
  const res = await fetch("http://127.0.0.1:8000/partners/analytics", { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to load analytics");
  return res.json();
}
export async function resetAssistantSession(sessionId: string) {
  const response = await fetch("http://127.0.0.1:8000/assistant/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });

  if (!response.ok) {
    throw new Error("Failed to reset assistant session");
  }

  return response.json();
}
